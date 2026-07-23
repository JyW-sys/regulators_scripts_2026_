# JO CBJ Regulatory Lists

Central Bank of Jordan (CBJ) — Jordan's central bank and financial regulator. Source: https://www.cbj.gov.jo. Jira: **DECD-5560** (epic DECD-3438, Regulators 2026 — Crawlers).

Five lists are scraped: two server-rendered HTML routes (banks table + card→detail pages) and two PDF registers. No JSON API exists. The site is very slow to first byte (tens of seconds per request) and intermittently drops connections, so every fetch uses a long timeout + retries and detail pages are fetched concurrently.

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| JO | CBJ | 1 | Directory of Banks | https://www.cbj.gov.jo/EN/Pages/Bankingsectorguide | Paginated HTML `<table>` (2 pages × 10 → 20 banks). The `/EN/Pages/*` route accepts a full-form `__doPostBack` POST, walked with `requests`. See the control-server pagination note below. Extract all entities. |
| JO | CBJ | 2 | Specialized Finance Company | https://www.cbj.gov.jo/EN/List/Specialized_Finance_Company | Card grid → detail pages. Pager is **broken server-side** (see note). Walked by detail index instead → 15 entities. |
| JO | CBJ | 3 | Microfinance Company | https://www.cbj.gov.jo/EN/List/Guide_of_Microfinance_Sector | Card grid → detail pages, single page. Walked by detail index → 9 cards, 7 active (2 inactive excluded). |
| JO | CBJ | 4 | Companies licensed under the Electronic Payment and Money Transfer Bylaw | https://www.cbj.gov.jo/En/List/Participants_in_Payments_and_Settlements_Systems  ·  PDF: https://www.cbj.gov.jo/EBV4.0/Root_Storage/AR/Domestic/A_general_register_of_licensed_companies.pdf | PDF (1 entity/page profiles + a money-exchange table). If the direct PDF link fails, discover it from the landing page under "**A general register of companies**". |
| JO | CBJ | 5 | Accredited international electronic payment systems | https://www.cbj.gov.jo/En/List/Participants_in_Payments_and_Settlements_Systems  ·  PDF: https://www.cbj.gov.jo/EBV4.0/Root_Storage/AR/Domestic/Register_of_accredited_international_electronic_payment_systems_.pdf | PDF (1 entity/page). If the direct PDF link fails, discover it from the landing page under "**Register of accredited international electronic payment systems**". |

## ListLabel

Per ticket owner: 1 = bank named in list name, 2 = insurance, 3 = bank & insurance, 4 = other. Only **List 1 (Directory of Banks) = 1**; Lists 2–5 = 4.

## Scope decisions (confirmed with ticket owner)

- **Inactive entities excluded.** Cancelled / revoked / insolvent / under-liquidation entities are dropped; output holds only currently-regulated entities (`RegulationType = Regulated`). E.g. List 3 excludes *Finca* (declared insolvent) and *Ethmar* (under liquidation).
- **List 4 includes everything:** the Central Bank of Jordan self-entry and the active money-exchange companies ARE included. The branches table lists sub-locations of already-captured companies, so it is treated as branch info, not separate entities.

## Pagination note — the "next page" button is broken server-side (Lists 2 & 3)

The `/EN/List/*` card grids render a numeric pager whose `__doPostBack` posts back to the same GET-only rewritten URL, which the CBJ server answers with **HTTP 404** — the page-turn fails even in a real browser. `requests` and Selenium both only ever see page 1, so v2 lost 6 of the 15 specialized finance companies.

**v3 fix — walk by detail index.** Every card links to `/EN/ListDetails/<slug>/<blockId>/<n>` where `<n>` is a small contiguous index. v3 reads `<blockId>` off page 1, then fetches detail pages for `n = 1, 2, …` in concurrent batches, stopping after a whole batch of "Page not found" pages. This reaches every entity regardless of the broken pager. Entity name comes from the detail "Company Name" field, falling back to the last breadcrumb crumb (some detail pages omit the name field).

## Pagination note — List 1 POST pager degraded on the control server

Unlike Lists 2 & 3, List 1's `/EN/Pages/*` POST pager works locally (20 banks) but returned **page 1 only (10 banks)** on the control server: GET works there, but the pager POST was being blocked — a bot `User-Agent`, missing postback headers, or a proxy stripping the POST body. The fix (in `JO_CBJ_v3.py`):

- send a **real-browser `User-Agent`** plus postback headers (`Content-Type` / `Referer` / `Origin`);
- **verify each POST actually advanced** the page — a stripped body makes the server re-serve page 1, which is now treated as a failure instead of silent success;
- **Selenium fallback** — if the `requests` POST path still walks only one page, drive a real headless browser through the pager (submitting the form directly, since a sticky footer intercepts native clicks) so every page is still collected. Deduped by Name.

**v4 fix — Edge on the control server.** v3's browser fallback started **Chrome only**, but the control server has no Chrome (Windows box with Edge + the repo's `edgedriver_win64` driver), so the fallback died at startup and List 1 still degraded to page 1's 10 banks there. v4's `start_headless_browser()` tries Chrome first, then **falls back to Edge** (preferring the bundled `edgedriver_win64/msedgedriver.exe`), for both the List 1 pager fallback and the List 4/5 PDF browser-download fallback.

## Versions

- **`JO_CBJ_v4.py`** — current. Same as v3 plus: (a) a Chrome→Edge headless-browser fallback (`start_headless_browser()`) for the control server (no Chrome, Edge only), where List 1 returned 10 of 20 banks; (b) after the xlsx is written, **one PDF per ListCode** is generated in `tempfolder/` (entity names, one per line, reportlab) — same deliverable as IT CONSOB / HU CBH: `<xlsx basename>- <ListCode>.pdf`.
- `JO_CBJ_v3.py` — Index-walk for Lists 2 & 3 (collects all pages); long timeouts + retries for the slow network. List 1 pager hardened for the control server (real UA + postback headers + advance verification + Selenium fallback, Chrome only). Selenium is also used as a PDF-download fallback for Lists 4 & 5.
- `JO_CBJ_v2.py` — prior. Selenium card-pager; captured page 1 only for List 2 (9 of 15).
- `JO_CBJ_v1.py` — initial.

## Output

`JO CBJ SQL Ready <timestamp>.xlsx` — fixed 43-column SQL-Ready schema (see project `CLAUDE.md`). Latest run: 89 rows — List 1: 20, List 2: 15, List 3: 7, List 4: 24, List 5: 23.

Additionally (v4), `tempfolder/JO CBJ SQL Ready <timestamp>- <ListCode>.pdf` — one PDF per list holding the entity names, generated with reportlab after the xlsx.
