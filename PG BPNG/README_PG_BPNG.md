# PG BPNG

## Regulator Information

- **Country/Region Code**: PG
- **Regulator Code**: BPNG
- **Full Name**: Bank of Papua New Guinea
- **Website**: https://www.bankpng.gov.pg/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6335

## Script

- **Current Version**: `PG_BPNG_v1.py`
- **Approach**: single HTML page behind a Cloudflare "Just a moment..." challenge (plain `requests` returns 403). Rendered with **DrissionPage** (real Chrome, same pattern as `DO SSDO`/`CW CBCSCW`), then parsed with BeautifulSoup.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Licensed Entities in Papua New Guinea | https://www.bankpng.gov.pg/financial-stability/licensed-entities | Extract all entities in this page |

## Page structure & parsing

The page has no tables — each license category is an `<h5>` heading followed by one `<p>` whose text is a run-on numbered list (`1. Name 2. Name 3. Name ...`). Two headings (`H) Life Insurance Institutions`, `I) Superannuation Institutions`) have their own `<h5>` sub-headings (`i.`, `ii.`, ...) instead of a single paragraph. The scraper walks `<h5>`/`<p>` in document order, tracks the current top-level (`A)`-`I)`) and sub-level (`i.`-`iv.`) label, and splits each numbered paragraph on the `N. ` marker.

There is **no address/phone/email/website** on this page — it is a name-only listing grouped by license type, so those fields are blank for every row.

13 license-type categories map to `License_Type`:

| License_Type | Count |
|---|---|
| Savings & Loan Societies | 18 |
| Licensed Financial Institutions (LFIs) | 12 |
| Authorised Bureau of Currency Exchanger (Money Changers) | 9 |
| Commercial Banks | 7 |
| Life Insurance Brokers | 6 |
| Life Insurance Companies | 4 |
| Authorised Superannuation Funds | 4 |
| Licensed Trustees | 4 |
| Licensed Investment Managers | 4 |
| Authorised Money Remitters | 3 |
| Licensed Fund Administrators | 3 |
| Authorised FX Dealers | 2 |
| Payment Service Provider | 1 |
| **Total** | **77** |

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | text of each numbered entry |
| License_Type | current `<h5>` category (sub-heading takes priority over top-level) |
| Cntry | `PG` |
| RegulationType | `Regulated` |
| ListName | `Licensed Entities in Papua New Guinea` |
| ListLabel | `4` — mixed list (banks, insurance, pension/superannuation, FX, remittance, payments); not a clean bank-only or insurance-only or bank+insurance split |
| ListLanguage | `EN` |
| RegCtry / RegCode / ListCode | PG / BPNG / 1 |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **Total 77 entities**, all under a single ListNr/ListCode as instructed by Jira.
- 3 expected cross-category duplicates (same entity holds two licenses, not a parsing error): *First Investment Finance Limited* and *Heduru Moni (Moni Plus) Limited* appear under both LFIs and FX Dealers; *MH Money Express (PNG) Limited* appears under both Money Remitters and Currency Exchangers.
- No baseline exists yet in `qa_positive_combined/` for this regulator (new folder).
- `ListLabel = 4` is a judgment call given the mixed category list — flagged for review since the project rule only defines 1/2/3 for bank/insurance/both.
