# ZM BZA

## Regulator Information

- **Country/Region Code**: ZM
- **Regulator Code**: BZA
- **Full Name**: Bank of Zambia
- **Website**: https://www.boz.zm/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6327

## Script

- **Current Version**: `ZM_BZA_v2.py` (supersedes `ZM_BZA_v1.py` — see "v2 corrections" below)
- **Approach**: the source page (`.../financial-stability/registered-financial-institutions`) is an Angular single-page app (`<app-root>`) — plain `requests` only returns the empty HTML shell. A one-off DrissionPage render (real Chrome) was used during exploration to pass the JS bootstrap and, via `dp.listen`, discover the public JSON API the page itself calls to populate its table and its four "named filter" summary cards:

  ```
  GET https://www.boz.zm/api/v1/views/registered_financial_institutions?page=N
  ```

  This endpoint is **not** behind Cloudflare/WAF — plain `requests` with a desktop User-Agent and `verify=False` returns clean JSON directly (confirmed with curl), so the production script talks to it directly with `requests` and needs no browser automation. It is paginated (25 records/page) and returns `[]` once exhausted; the script pages through until empty and saves the combined raw JSON to `ZM BZA/tempfolder/registered_financial_institutions_raw.json`.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Registered Commercial Banks | https://www.boz.zm/financial-stability/registered-financial-institutions | Click the named filter and extract the entities |
| 2 | Registered Non-Bank Financial Institutions | (same page) | Click the named filter and extract the entities, remove "liquidated institutions" |
| 3 | Deposit Taking Non-Banks | (same page) | NEW LIST! Click the named filter and extract the entities |
| 4 | Payment System Institutions | (same page) | NEW LIST! Click the named filter and extract the entities |

All four lists are the four "named filter" summary cards on one single page — only ListNr 1 has its own URL in Jira, the other three rows have no URL because they are additional filters on that same page.

## Page structure & parsing

The rendered page shows a single institutions table with four clickable "summary card" filters above it (`Registered Commercial Banks` / `Registered non-bank institutions` / `Deposit taking Non-banks` / `Payment Systems`), each showing a live count. Under the hood, every record returned by the JSON API carries a `type` field that cleanly partitions the data into three underlying Drupal content types, which in turn map onto the four Jira lists:

| API `type` | subcategory field | Jira list |
|---|---|---|
| `banks_and_deposit_non_banks` | `field_commercial_bank_non_bank` = "Commercial Banks" | ListNr 1 |
| `banks_and_deposit_non_banks` | `field_commercial_bank_non_bank` = "Deposit Taking Non-Banks" | ListNr 3 |
| `non_bank_financial_institution` | `field_institution_category` != "Liquidated Institutions" | ListNr 2 |
| `non_bank_financial_institution` | `field_institution_category` == "Liquidated Institutions" | **excluded** (per Jira comment) |
| `payment_system_institutions` | `field_payment_system_type` (Participants/Businesses/Systems) | ListNr 4 |

Field availability differs cleanly and consistently by `type` (verified empirically across all 216 raw records, no overlap):

- `banks_and_deposit_non_banks` → `field_city`, `field_postal_address`, `field_telephone`, `field_short_name`
- `non_bank_financial_institution` → `field_institution_address`, `field_institution_city`, `field_email`, `field_institution_telephone`
- `payment_system_institutions` → `field_address` only (single free-text field; no separate city/phone/email on this content type)

All text fields arrive as raw Drupal HTML fragments (e.g. `<a href="/taxonomy/term/413">Commercial Banks</a>`, `<p>...</p>`); the scraper strips tags, unescapes HTML entities (`&amp;`, `&nbsp;`), and collapses whitespace.

**Source data-quality quirk**: roughly half (47/89 after duplicate collapse) of the `payment_system_institutions` records have `field_address` populated with a lone `"."` placeholder rather than a real address or being left empty. The scraper detects this pattern and blanks it to an empty string rather than reporting `"."` as a real address — reflected in the Address_1 non-empty rate for ListNr 4 below.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | `title` (institution name, HTML-stripped) |
| License_Type | List 1/3: `field_commercial_bank_non_bank`; List 2: `field_institution_category`; List 4: `field_payment_system_type` + `field_payment_system_license_s` in parentheses, e.g. `DESIGNATED PAYMENT SYSTEM PARTICIPANTS (CIC, DDACC, ZIPSS/RTGS)` |
| Address_1 | List 1/3: `field_postal_address`; List 2: `field_institution_address`; List 4: `field_address` (placeholder `"."` values blanked) |
| City | List 1/3: `field_city`; List 2: `field_institution_city`; List 4: town parsed out of the free-text `field_address` (no separate city field on this content type) |
| Phone | List 1/3: `field_telephone`; List 2: `field_institution_telephone`; List 4: blank |
| Email | List 2: `field_email`; Lists 1/3/4: blank (field not populated on those content types) |
| Website | blank for all lists — not present anywhere in the API response |
| Cntry | `ZM` |
| RegulationType | `Regulated` (all four lists are current in-force registrations; liquidated institutions are excluded entirely, not marked cancelled) |
| ListName | Jira `ListName` verbatim (per ListNr) |
| ListLabel | see judgment calls below |
| ListLanguage | `EN` |
| RegCtry / RegCode | ZM / BZA |
| ListCode | Jira ListNr (1-4) |
| RegulationDate | List 4: `field_month_year_of_designation` from `/jsonapi/node/payment_system_institutions`, joined by node id; blank for Lists 1-3 (not published) |
| ListProcessDate | run date (`%Y-%m-%d`) |

## ListLabel judgment calls

Per CLAUDE.md: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else, assigned per ListNr.

- **ListNr 1 (Registered Commercial Banks) → 1**. Unambiguous bank list.
- **ListNr 3 (Deposit Taking Non-Banks) → 1**. BOZ's own data model groups this together with Commercial Banks under one API `type` (`banks_and_deposit_non_banks`) — these are prudentially-supervised deposit-taking financial institutions, treated as bank-adjacent under the project's existing convention (e.g. `KE CBK` assigns ListLabel 1 to "Microfinance Banks", a comparable deposit-taking-but-not-commercial-bank category).
- **ListNr 2 (Registered Non-Bank Financial Institutions) → 4**. This bucket mixes Microfinance Institutions, Bureaux De Change, Leasing and Finance Companies, Credit Reference Bureaus, and Development Finance Institutions — none of which is a clean bank or insurance category, and it is explicitly *not* deposit-taking (BOZ keeps it in a separate API `type` from Commercial Banks/Deposit Taking Non-Banks). Matches how the project labels comparable non-bank categories elsewhere (e.g. `KE CBK` labels Forex Bureaus / Credit Reference Bureaus / Money Remittance as 4).
- **ListNr 4 (Payment System Institutions) → 4**. Payment systems/aggregators/switches are neither a bank nor insurance list under this project's convention (consistent with how payment-system and money-remittance lists are labeled `4` elsewhere in the repo, e.g. `PG BPNG`).

## Notes / QA

**Row counts** (v2, run date 2026-08-05), all four lists on one page, fetched via the JSON API (216 raw records → 213 after collapsing same-title duplicates, exactly what the site prints):

| ListCode | ListName | Site count | Rows |
|---|---|---|---|
| 1 | Registered Commercial Banks | 15 | 15 |
| 2 | Registered Non-Bank Financial Institutions | 100 − 9 liquidated = 91 | 91 |
| 3 | Deposit Taking Non-Banks | 9 | 9 |
| 4 | Payment System Institutions | 89 | 89 |
| — | *(excluded: Liquidated Institutions, per Jira comment)* | 9 | — |
| **Total output rows** | | | **204** |

The site's own footer reads *"Showing 1-10 of 213 institutions"* and its four named filter cards read **15 / 100 / 9 / 89**; clicking each filter was verified live. Every list now reconciles to the site exactly.

**v2 corrections (v1 output was wrong):**

- **List 4 over-counted by 2.** The raw feed returns 216 records but the site renders 213: the Angular front-end collapses records sharing a title inside one content type. There are exactly three such pairs — `BEELINE FINTECH LIMITED` (nodes 113831/113832), `JustTap Payments Limited` (3611/3138), `Access Financial Services Limited` (3381/3656, both liquidated). All six nodes are published (`status: true`), so these are genuine CMS content duplicates, not a publish-state filter. v1 emitted both of each payment-system pair (91 rows); v2 keeps the *richer* record of each pair — node 3611 "JustTap" carries an empty address while 3138 has the real one — giving 89, matching the site. This is not "deduping rows that appear separately": the site itself prints a single row for each, confirmed on the rendered grid.
- **v1's reconciliation of List 2 was wrong.** v1's README claimed the site's non-bank card (then read as 99) bundled List 2 + List 3. It does not: the card counts the `non_bank_financial_institution` content type only, *including* liquidated institutions — `91 non-liquidated + 9 liquidated = 100`. Deposit Taking Non-Banks is a separate card (9) sourced from a different content type.
- **List 2 gained one entity**: `ASA MICROFINANCE ZAMBIA LIMITED`, added by BOZ after the 2026-07-27 run (90 → 91).
- **RegulationDate now populated for List 4.** The Drupal JSON:API node feed `/jsonapi/node/payment_system_institutions` exposes `field_month_year_of_designation` as a clean ISO date for all 91 payment-system nodes, joined by node id. The on-page grid column "Licensed Since" shows `-` only because that view omits the field. No equivalent date exists for Lists 1-3.
- **City now recovered for List 4.** That content type has no city field, but its free-text `field_address` ends in the town; the town is matched against a Zambian town list (41 of the 43 non-empty addresses resolve; the 2 misses are the BEELINE "ZNFU Office Complex … Showground Area" address, which names no town).

**Non-empty rates** (204 rows):
- Name: 204/204 (100%), Cntry / RegCtry / RegCode / ListLanguage / ListLabel / RegulationType / ListProcessDate / License_Type: 100%
- Address_1: 156/204 (76.5%) — List 1: 15/15, List 2: 91/91, List 3: 8/9 (`LOLC FINANCE ZAMBIA` has no postal address on file), List 4: 42/89 (47 payment-system records carry only a junk `"."` placeholder or nothing at source, blanked rather than reported as real data)
- City: 156/204 (76.5%) — Lists 1-3 complete (100%); List 4: 41/89, derived from the address text as described above
- Phone: 113/204 (55%) — only provided for Lists 1-3 (List 1: 15/15, List 2: 89/91, List 3: 9/9); List 4 has no phone field on that content type
- RegulationDate: 89/204 (44%) — List 4 only (designation date); not published for Lists 1-3
- Email: 65/204 (32%) — only populated on List 2's content type; blank for Lists 1, 3, 4 (field not used on those content types)
- Website: 0/204 (0%) — not present anywhere in the source API for any list; genuinely absent, not a parsing gap

**Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` — 0 flagged rows, clean.

**Duplicate Names**: 14 rows across 7 names.
- 5 are legitimate cross-category entities regulated under two different lists (expected, not a bug): `BAYPORT FINANCIAL SERVICES LIMITED`, `FINCA ZAMBIA LIMITED`, `MADISON FINANCE COMPANY LIMITED`, `NATIONAL SAVINGS AND CREDIT BANK`, `ZAMBIA NATIONAL BUILDING SOCIETY` — each is both a Deposit Taking Non-Bank (List 3) and a Payment System Business (List 4).
- 2 are genuine source-side duplicate CMS entries (same name, same List 4 category, but different node IDs on BOZ's own site — confirmed in the raw JSON, e.g. `BEELINE FINTECH LIMITED` at `/node/113831` and `/node/113832`, `JustTap Payments Limited` at `/node/3138` and `/node/3611`): a data-quality artifact of the source, not a parsing bug. The same duplication pattern was also observed (and excluded along with the rest of that category) in the 10 Liquidated Institutions records, e.g. "Access Financial Services Limited" appears twice.
- No de-duplication was applied — both source rows are kept as-is per the project's practice of reflecting the source faithfully rather than silently dropping records.

**Translation**: source is entirely in English; no translation needed.

**Blockers**: none — all four lists were successfully scraped from the single source page/API.

- No baseline exists yet in `qa_positive_combined/` for this regulator (new folder, greenfield ticket).
