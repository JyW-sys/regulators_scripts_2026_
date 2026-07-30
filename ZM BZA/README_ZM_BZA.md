# ZM BZA

## Regulator Information

- **Country/Region Code**: ZM
- **Regulator Code**: BZA
- **Full Name**: Bank of Zambia
- **Website**: https://www.boz.zm/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6327

## Script

- **Current Version**: `ZM_BZA_v1.py`
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

Field availability differs cleanly and consistently by `type` (verified empirically across all 215 raw records, no overlap):

- `banks_and_deposit_non_banks` → `field_city`, `field_postal_address`, `field_telephone`, `field_short_name`
- `non_bank_financial_institution` → `field_institution_address`, `field_institution_city`, `field_email`, `field_institution_telephone`
- `payment_system_institutions` → `field_address` only (single free-text field; no separate city/phone/email on this content type)

All text fields arrive as raw Drupal HTML fragments (e.g. `<a href="/taxonomy/term/413">Commercial Banks</a>`, `<p>...</p>`); the scraper strips tags, unescapes HTML entities (`&amp;`, `&nbsp;`), and collapses whitespace.

**Source data-quality quirk**: roughly half (48/91) of the `payment_system_institutions` records have `field_address` populated with a lone `"."` placeholder rather than a real address or being left empty. The scraper detects this pattern and blanks it to an empty string rather than reporting `"."` as a real address — reflected in the Address_1 non-empty rate for ListNr 4 below.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | `title` (institution name, HTML-stripped) |
| License_Type | List 1/3: `field_commercial_bank_non_bank`; List 2: `field_institution_category`; List 4: `field_payment_system_type` + `field_payment_system_license_s` in parentheses, e.g. `DESIGNATED PAYMENT SYSTEM PARTICIPANTS (CIC, DDACC, ZIPSS/RTGS)` |
| Address_1 | List 1/3: `field_postal_address`; List 2: `field_institution_address`; List 4: `field_address` (placeholder `"."` values blanked) |
| City | List 1/3: `field_city`; List 2: `field_institution_city`; List 4: blank (not a separate field on this content type) |
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
| ListProcessDate | run date (`%Y-%m-%d`) |

## ListLabel judgment calls

Per CLAUDE.md: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else, assigned per ListNr.

- **ListNr 1 (Registered Commercial Banks) → 1**. Unambiguous bank list.
- **ListNr 3 (Deposit Taking Non-Banks) → 1**. BOZ's own data model groups this together with Commercial Banks under one API `type` (`banks_and_deposit_non_banks`) — these are prudentially-supervised deposit-taking financial institutions, treated as bank-adjacent under the project's existing convention (e.g. `KE CBK` assigns ListLabel 1 to "Microfinance Banks", a comparable deposit-taking-but-not-commercial-bank category).
- **ListNr 2 (Registered Non-Bank Financial Institutions) → 4**. This bucket mixes Microfinance Institutions, Bureaux De Change, Leasing and Finance Companies, Credit Reference Bureaus, and Development Finance Institutions — none of which is a clean bank or insurance category, and it is explicitly *not* deposit-taking (BOZ keeps it in a separate API `type` from Commercial Banks/Deposit Taking Non-Banks). Matches how the project labels comparable non-bank categories elsewhere (e.g. `KE CBK` labels Forex Bureaus / Credit Reference Bureaus / Money Remittance as 4).
- **ListNr 4 (Payment System Institutions) → 4**. Payment systems/aggregators/switches are neither a bank nor insurance list under this project's convention (consistent with how payment-system and money-remittance lists are labeled `4` elsewhere in the repo, e.g. `PG BPNG`).

## Notes / QA

**Row counts** (run date 2026-07-27), all four lists on one page, fetched via the JSON API (215 raw records total):

| ListCode | ListName | Rows |
|---|---|---|
| 1 | Registered Commercial Banks | 15 |
| 2 | Registered Non-Bank Financial Institutions | 90 |
| 3 | Deposit Taking Non-Banks | 9 |
| 4 | Payment System Institutions | 91 |
| — | *(excluded: Liquidated Institutions, per Jira comment)* | 10 |
| **Total output rows** | | **205** |

On-page summary-card counts at scrape time: 15 / 99 / 9 / 89 (Commercial Banks / non-bank institutions / Deposit Taking Non-Banks / Payment Systems). List 1 and List 3 match exactly (15, 9). Lists 2 and 4 look off at first glance but both reconcile exactly once the site's own aggregation logic is accounted for:

- **List 2 (90 vs. site's 99)**: the site's "Registered non-bank institutions" card is **not** List 2 alone — it bundles List 2 + List 3 together: `90 (Non-Bank FI, excl. liquidated) + 9 (Deposit Taking Non-Banks) = 99`, an exact match. BOZ's own widget doesn't distinguish deposit-taking-ness within its non-bank count, but the Jira ticket explicitly asks for them as two separate lists (ListNr 2 vs. ListNr 3) — our split is correct per Jira, it just isn't how the site chooses to display the aggregate.
- **List 4 (91 vs. site's 89)**: an exact difference of 2, matching the 2 duplicate CMS node pairs identified below (`BEELINE FINTECH LIMITED`, `JustTap Payments Limited` — each has two distinct node IDs in the raw feed for the same name). The site widget appears to count unique institution names (89); our scrape keeps both source records per the project's practice of reflecting the source faithfully rather than silently deduping.

The API-derived counts are the authoritative source (every paginated record enumerated), and every count above is now traced to source, not left as an unexplained delta.

**Non-empty rates** (205 rows):
- Name: 205/205 (100%), Cntry: 205/205 (100%), License_Type: 205/205 (100%)
- Address_1: 156/205 (76%) — List 1: 15/15, List 2: 90/90, List 3: 8/9 (one bank, `LOLC FINANCE ZAMBIA`, has no postal address on file), List 4: 43/91 (48 of the 91 payment-system records have only a junk `"."` placeholder on the source, blanked rather than reported as real data)
- Phone: 112/205 (55%) — only provided for Lists 1-3 (List 1: 15/15, List 2: 88/90, List 3: 9/9); List 4 has no phone field on that content type
- City: 114/205 (56%) — same pattern as Phone (blank for List 4 by content-type design)
- Email: 65/205 (32%) — only populated on List 2's content type; blank for Lists 1, 3, 4 (field not used on those content types)
- Website: 0/205 (0%) — not present anywhere in the source API for any list; genuinely absent, not a parsing gap

**Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` — 0 flagged rows, clean.

**Duplicate Names**: 14 rows across 7 names.
- 5 are legitimate cross-category entities regulated under two different lists (expected, not a bug): `BAYPORT FINANCIAL SERVICES LIMITED`, `FINCA ZAMBIA LIMITED`, `MADISON FINANCE COMPANY LIMITED`, `NATIONAL SAVINGS AND CREDIT BANK`, `ZAMBIA NATIONAL BUILDING SOCIETY` — each is both a Deposit Taking Non-Bank (List 3) and a Payment System Business (List 4).
- 2 are genuine source-side duplicate CMS entries (same name, same List 4 category, but different node IDs on BOZ's own site — confirmed in the raw JSON, e.g. `BEELINE FINTECH LIMITED` at `/node/113831` and `/node/113832`, `JustTap Payments Limited` at `/node/3138` and `/node/3611`): a data-quality artifact of the source, not a parsing bug. The same duplication pattern was also observed (and excluded along with the rest of that category) in the 10 Liquidated Institutions records, e.g. "Access Financial Services Limited" appears twice.
- No de-duplication was applied — both source rows are kept as-is per the project's practice of reflecting the source faithfully rather than silently dropping records.

**Translation**: source is entirely in English; no translation needed.

**Blockers**: none — all four lists were successfully scraped from the single source page/API.

- No baseline exists yet in `qa_positive_combined/` for this regulator (new folder, greenfield ticket).
