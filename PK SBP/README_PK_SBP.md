# PK SBP

## Regulator Information

- **Country/Region Code**: PK
- **Regulator Code**: SBP
- **Full Name**: State Bank of Pakistan
- **Website**: https://www.sbp.org.pk/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6336

## Script

- **Current Version**: `PK_SBP_v1.py`
- **Approach**: 6 separate "sbp-regulated-institutions" pages. All 6 shell pages return a clean HTTP 200 to plain `requests` (no Cloudflare/WAF), but the entity content itself is not in the shell HTML — each page embeds one or more `<div class="ajax-slot" data-url="https://www.sbp.org.pk/t_inner/oo-tabs/sbp-regulated-institutions/<slug>?i=N">` placeholders that are normally filled in by client-side JS. The scraper regex-extracts those `data-url` values from the shell page and fetches each ajax fragment directly with `requests` (also HTTP 200, no browser rendering needed), then parses the returned HTML with BeautifulSoup.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Commercial Banks | https://www.sbp.org.pk/sbp-regulated-institutions/commercial-banks | Extract all entities from each sub category of this page. |
| 2 | Microfinance Banks | https://www.sbp.org.pk/sbp-regulated-institutions/microfinance-banks | NEW LIST! Extract all entities from this page. |
| 3 | Exchange Companies | https://www.sbp.org.pk/sbp-regulated-institutions/exchange-companies | NEW LIST! Extract all entities from this page. |
| 4 | Development Finance Institutions | https://www.sbp.org.pk/sbp-regulated-institutions/development-finance-institutions | NEW LIST! Extract all entities from this page. |
| 5 | Payment System Operators | https://www.sbp.org.pk/sbp-regulated-institutions/payment-system-operators | NEW LIST! Extract all entities from this page. |
| 6 | Credit Bureaus | https://www.sbp.org.pk/sbp-regulated-institutions/credit-bureaus | NEW LIST! Extract all entities from this page. |

## Page structure & parsing

Each "sbp-regulated-institutions" shell page has an "On this Page" table of contents. The **Commercial Banks** page is the only one with multiple sub-categories/anchors (Digital Banks, Public Sector Commercial Banks, Specialized Banks, Local Private Banks, Islamic Banks, Foreign Banks) and correspondingly 6 `ajax-slot` URLs (`?i=1` .. `?i=6`); every other page has exactly 1 anchor/ajax-slot covering its whole list. Per the Jira Comments field ("Extract all entities from each sub category of this page"), the scraper fetches **all** ajax slots found on a page and merges their entities into that one ListNr.

Each ajax fragment renders one category as a Bootstrap vertical nav-tabs widget: one `<button class="nav-link">` per entity (button text = entity name) paired with a `<div class="tab-pane" id="...">` holding, in order:

- an `<h5>` (or a `<p><strong>...</strong></p>`) heading naming the head officer's title (`President`, `CEO`, `President/CEO`, `Managing Director`, `Country Head/President`, `GM/Chief Executive`, etc.) followed by `<p>` blocks: the officer's name, then the **head-office address**, then `Tel :` / `Fax:` lines.
- a `Complaint Cell` heading followed by `<p>` blocks with the complaint address, `Tel/UAN/PABX/Landline/Fax` lines, and `<a>` links (website + `mailto:` email).
- a `License / Permissions / Authorizations` heading followed by a `<ul><li>` list of the entity's actual SBP license/permission types.

A duplicate mobile-only `<div class="accordion">` block repeats the exact same per-entity content for responsive layout — **only** the desktop `<div class="tab-pane">` blocks are parsed, to avoid double-counting every entity.

Parsing quirks handled:
- The head-officer's **name** (e.g. "Mr. Muhammad Amir Khan") is identified and skipped (no field for it in the schema) using a heuristic: matches an honorific prefix (Mr/Mrs/Ms/Dr/Syed/...), or is a short (≤4-word) line with no digits/commas. Everything else in the head section is treated as address text — this correctly keeps addresses that happen to start with an honorific-like word (e.g. First Women Bank Limited's office is in the "**Dr.** Syedna Tahir Saifuddin Memorial Foundation Building").
- `Tel`/`Phone`/`Mobile`/`UAN`/`PABX`/`Landline`/`Fax` labels (with a required `:` delimiter) are regex-matched to pull Phone/Fax out of the head section specifically (complaint-cell phone/fax is not separately mapped — Address_1/Phone/Fax follow the head office, Website/Email follow the complaint-cell links, matching how the two sections are actually used on the source).
- City is derived by matching the address text against a curated list of major Pakistani cities (Karachi, Lahore, Islamabad, Rawalpindi, Peshawar, Bahawalpur, Gujrat, ...), taking the earliest-occurring match — this correctly picks "Karachi" (the primary/registered office) for the one entity (MCB Bank Limited) whose address block lists both a Karachi head office and a Lahore secretariat office.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | nav-tab button text (== entity name) |
| Address_1 | head-office address lines, joined with `, ` |
| City | matched from Address_1 against a curated Pakistani-city list |
| Phone / Fax | `Tel`/`Mobile`/`UAN`/`PABX`/`Landline` / `Fax` line in the head-office section |
| Website | first non-mailto `<a href>` found in the entity block (usually in the Complaint Cell section) |
| Email | first `mailto:` link, or a plain-text `Email:`/`Emails:` line if no link is present |
| License_Type | the `<ul><li>` items under "License / Permissions / Authorizations", joined with `; ` |
| Cntry | `PK` |
| RegulationType | `Regulated` |
| ListName / ListCode | verbatim from Jira / ListNr |
| ListLabel | see below |
| ListLanguage | `EN` (site content is in English) |
| RegCtry / RegCode | `PK` / `SBP` |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

**Row counts** (89 total, matches the live page counts exactly):

| ListCode | ListName | Rows | ListLabel |
|---|---|---|---|
| 1 | Commercial Banks | 33 (3 Digital + 4 Public Sector + 2 Specialized + 14 Local Private + 6 Islamic + 4 Foreign) | 1 |
| 2 | Microfinance Banks | 11 | 1 |
| 3 | Exchange Companies | 31 | 4 |
| 4 | Development Finance Institutions | 9 | 4 |
| 5 | Payment System Operators | 3 | 4 |
| 6 | Credit Bureaus | 2 | 4 |

**ListLabel judgment calls**: Commercial Banks and Microfinance Banks are both SBP-licensed **banking** categories -> `ListLabel = 1`. Exchange Companies, Development Finance Institutions, Payment System Operators, and Credit Bureaus are non-bank/non-insurance financial entities -> `ListLabel = 4`. Development Finance Institutions in particular is a judgment call — DFIs are wholesale/non-deposit-taking financial institutions regulated by SBP under a separate license class from commercial banks, so they were **not** folded into the bank list (`ListLabel=1`); flagged here for review.

**Non-empty rates**:
- Name / Cntry / Address_1 / City: 89/89 (100%)
- Phone: 81/89 (91%) — the 8 blanks are all Exchange Companies (ListCode 3) whose entity block genuinely has no `Tel`/phone line at all on the source page (verified against raw HTML for 2 of the 8: ABL Exchange, Alfalah Currency Exchange), not a parsing gap.
- Website / Email: 57/89 (64%) each — blank for all 31 Exchange Companies (their block has only CEO/address/license, no Complaint Cell section with links at all), plus Bank of China Limited (no website link on source, only a `mailto:`) and Deutsche Bank AG (only a website link, no `mailto:` on source). All verified genuine against the raw HTML, not parsing gaps.
- License_Type: 88/89 (99%) — blank only for ASA Microfinance Bank (Pakistan) Ltd, whose "License/Permissions/Authorizations:" label is present on the page but is **not** followed by any `<ul>` (verified in raw HTML) — a genuine gap on SBP's own page, not a parser miss.

**Encoding**: no `Ã©|â€™|Â |Ã¯|\?{3,}` red flags found — content is native English, no mojibake.

**Duplicates**: no duplicate `Name` values across the full 89-row output (checked across all 6 lists combined).

**Translation**: not applicable — all 6 SBP pages are in English.

**Blockers**: none. All 6 lists were accessible and fully scraped; no domain-level blocks, no CAPTCHA/WAF challenge encountered (plain `requests` sufficed for both the shell pages and the ajax fragments — DrissionPage was not needed).

No baseline exists yet in `qa_positive_combined/` for this regulator (new folder, greenfield).
