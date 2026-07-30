# NG CBNI

## Regulator Information

- **Country/Region Code**: NG
- **Regulator Code**: CBNI
- **Full Name**: Central Bank of Nigeria
- **Website**: https://www.cbn.gov.ng/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6334

## Script

- **Current Version**: `NG_CBNI_v1.py`
- **Approach**: Each of the 12 Jira lists is a page at `https://www.cbn.gov.ng/supervision/Inst-XX.html` whose Kendo grid ("Click the button to download the Excel file...") is populated client-side by a small JSON roster API (`https://www.cbn.gov.ng/api/GetXxx`). No Cloudflare/WAF challenge was encountered on this domain — plain `requests` (desktop User-Agent, `verify=False`, `urllib3` warnings disabled) returns HTTP 200 directly, so no DrissionPage fallback was needed anywhere. The Jira comment "click on each company in the website ... extract the information" refers to each entity's detail page `fi.html?id=<id>`, which is itself populated from `/api/GetFinInstById/<id>` — a JSON record with address, phone, email, website, institution type, licence category, ownership type and licence date. The script fetches that endpoint once per entity (8-way threaded, since one list has 829 entities) to enrich every row.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Commercial banks | https://www.cbn.gov.ng/supervision/Inst-DM.html | Roster API `GetDMBs` |
| 2 | Development Finance Institutions | https://www.cbn.gov.ng/supervision/Inst-DFI.html | Roster API `GetDFIs` |
| 3 | Discount Houses | https://www.cbn.gov.ng/supervision/Inst-DH.html | Roster API `GetDHs` |
| 4 | Finance Companies | https://www.cbn.gov.ng/supervision/Inst-FC.html | Roster API `GetFCs` |
| 5 | Merchant Banks | https://www.cbn.gov.ng/supervision/Inst-MB.html | Roster API `GetMBs` |
| 6 | Micro-Finance Banks | https://www.cbn.gov.ng/supervision/Inst-MF.html | Roster API `GetMFBs` |
| 7 | Non-Interest Banks | https://www.cbn.gov.ng/supervision/Inst-NI.html | Roster API `GetNIBs` |
| 8 | Primary Mortgage Institution | https://www.cbn.gov.ng/supervision/Inst-PMI.html | Roster API `GetPMIs` |
| 9 | Bureau de Change | https://www.cbn.gov.ng/supervision/Inst-BDC.html | Tier 1 + Tier 2 grids on the same page, roster APIs `GetBDCsTier1` + `GetBDCsTier2`, combined into one ListNr per Jira |
| 10 | Holding Companies | https://www.cbn.gov.ng/supervision/Inst-HC.html | Roster API `GetHCs`; NEW LIST |
| 11 | Mobile Money Operators | https://www.cbn.gov.ng/supervision/Inst-MMO.html | Roster API `GetMMOs`; NEW LIST |
| 12 | Payment Service Banks | https://www.cbn.gov.ng/supervision/Inst-PSB.html | Roster API `GetPSBs`; NEW LIST |

## Page structure & parsing

All 12 pages share the same structure: a Kendo UI grid bound to a `transport.read.url` JSON endpoint (`/api/GetXxx`), each row templated as `<a href="fi.html?id=#=id#">#=name#</a>`. The roster JSON itself only reliably carries `id`/`name` (all other fields are `null` at the roster level); the real per-entity data lives behind `/api/GetFinInstById/<id>`, which is what `fi.html?id=<id>` calls client-side and renders into a label/value table. The scraper calls the roster endpoint once per list (twice for Bureau de Change, one call per tier, then concatenates), then calls the detail endpoint once per entity id.

**Known source-side data-quality issue (not a scraper bug):** `GetFinInstById` returns HTTP 500 for a substantial, consistent subset of ids across most lists (confirmed reproducible on retry with delays, and confirmed independently by loading `fi.html?id=<failing id>` in a real Chrome browser via DrissionPage — the live public website's own JS `fetch()` call to the same endpoint fails identically and the detail table renders empty). This is a bug in CBN's backend, not something fixable from the client side. Affected rows keep the entity `Name` from the roster API; all detail fields (address/phone/email/website/licence date/etc.) are left blank rather than fabricated.

**Nigerian state abbreviations**: CBN's own `state` field is inconsistently truncated for a chunk of records (e.g. `ANA` instead of `Anambra`, `LAG` instead of `Lagos`, `OGU` instead of `Ogun`) — this comes straight off the API, confirmed not a parsing artifact. Since Nigeria's 36 states + FCT are a fixed, known list of proper nouns, the script canonicalizes via unambiguous prefix match against that list (e.g. `ANA` → the only state starting with "ana" is `Anambra`) rather than leaving inconsistent abbreviations or guessing. This is a deterministic lookup, not fabricated data.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | `name` (detail API; falls back to roster API name if detail is missing) |
| InternalID_1 / InternalID_1_type | CBN's internal numeric id (used in `fi.html?id=`) / `'CBN ID'` |
| CoType | `institutetype` (e.g. `Commercial Bank`, `MicroFinance Bank`, `Bureau De Change`) |
| License_Type | `categorization` — licence tier/category (e.g. `International`/`National`/`Regional` for commercial banks, `TIER 1`/`TIER 2` for BDCs, `STATE MFB`/`NATIONAL MFB` for microfinance banks) |
| Typology | `ownershiptype` (`Domestic` / `Foreign` / `Foreign and Domestic`) |
| Address_1 | `streetAddress` |
| Address_2 | `postalAddress` when present and different from `streetAddress`, else `area` |
| City | `state`, canonicalized against Nigeria's 36 states + FCT (see above) |
| Phone / Fax | `telephoneNo` / `faxNo` |
| Website / Email | `website` / `email` (lower-cased) |
| RegulationDate | `datelicensed`, **raw as printed** (formats vary: `10/28/2024`, `3rd January, 2006`, `5th Feb, 2001 (previously licensed Dec. 19, 1988)`) |
| Cntry | `NG` |
| RegulationType | `Regulated` |
| ListName | exact Jira ListName per table above |
| ListLabel | `1` (bank) or `4` (other) — see judgment call below |
| ListLanguage | `EN` |
| RegCtry / RegCode / ListCode | `NG` / `CBNI` / 1–12 |
| ListProcessDate | run date (`%Y-%m-%d`) |

### ListLabel judgment call

CBN does not regulate insurance in Nigeria (that is NAICOM's remit), so none of the 12 lists is insurance — the "genuine mix" across 12 lists is bank vs. other, not bank vs. insurance:

- **ListLabel = 1 (bank)**: Commercial banks, Development Finance Institutions, Discount Houses, Merchant Banks, Micro-Finance Banks, Non-Interest Banks, Primary Mortgage Institution, Payment Service Banks — all licensed as bank categories under Nigeria's Banks and Other Financial Institutions Act (BOFIA), or (for DFIs) are government development banks.
- **ListLabel = 4 (other)**: Finance Companies, Bureau de Change, Holding Companies, Mobile Money Operators — non-bank financial institutions (Finance Companies and BDCs are explicitly non-deposit-taking NBFIs; Holding Companies own bank/financial subsidiaries but are not themselves a bank; Mobile Money Operators are fintech/payments entities).

## Notes / QA

**Row counts per ListNr** (12/12 lists populated, none skipped/blocked — total **1152** rows):

| ListCode | ListName | Rows | Detail enrichment OK / total |
|---|---|---|---|
| 1 | Commercial banks | 28 | 21/28 |
| 2 | Development Finance Institutions | 8 | 8/8 |
| 3 | Discount Houses | 5 | 0/5 |
| 4 | Finance Companies | 126 | 31/126 |
| 5 | Merchant Banks | 6 | 2/6 |
| 6 | Micro-Finance Banks | 829 | 160/829 |
| 7 | Non-Interest Banks | 6 | 3/6 |
| 8 | Primary Mortgage Institution | 33 | 1/33 |
| 9 | Bureau de Change | 82 | 81/82 |
| 10 | Holding Companies | 7 | 1/7 |
| 11 | Mobile Money Operators | 17 | 17/17 |
| 12 | Payment Service Banks | 5 | 2/5 |
| **Total** | | **1152** | **327/1152 (28%)** |

- **Name / Cntry**: 1152/1152 (100%) — every row has a name (roster API always supplies this even when the detail call 500s) and `Cntry = NG`.
- **Address_1 / City / CoType / License_Type / RegulationDate**: 327/1152 (28%) non-empty — exactly the rows whose `GetFinInstById` call succeeded (HTTP 500 on the rest, a CBN backend bug — see Page structure & parsing above). This is a genuine source-side data gap, not a parsing gap: it affects some lists severely (Discount Houses 0/5, Primary Mortgage Institution 1/33, Holding Companies 1/7, Micro-Finance Banks 160/829) and others barely at all (Development Finance Institutions 8/8, Mobile Money Operators 17/17, Bureau de Change 81/82).
- **Phone**: 283/1152 (25%, subset of the 327 detail-enriched rows — a few of those have a blank `telephoneNo` on CBN's own record).
- **Website / Email**: 16/1152 and 34/1152 — CBN's directory simply doesn't publish these for most entities (most rows that do have a website are large commercial banks).
- **Encoding check** (`Ã©|â€™|Â |Ã¯|\?{3,}`): clean, 0 hits across all columns.
- **Duplicate `Name` values**: 3 pairs, **all within List 6 (Micro-Finance Banks)**, none cross-list:
  - `BWAY Microfinance bank Limited` (CBN ids 10029 / 10030, both `TIER 1 UNIT`)
  - `Katsu Microfinance Bank Limited` (ids 10048 `TIER 2 UNIT` / 10009 `TIER 2`)
  - `Paragon Microfinance Bank Limited` (ids 10011 / 10012, both `TIER 2 UNIT`)

  These are duplicate roster entries in CBN's own MFB database (same institution name under two internal ids) — a source data-quality artifact, not a parsing bug. Since the 12 CBN lists are 12 mutually-exclusive institution-type categories (unlike some other regulators' overlapping list sets), **no cross-list duplicates were found or expected** — confirmed programmatically (zero entity names span more than one `ListCode`).
- No `qa_positive_combined/` baseline exists for this regulator — greenfield, as expected.
- No lists were blocked or skipped; all 12 Jira rows are represented in the output.
