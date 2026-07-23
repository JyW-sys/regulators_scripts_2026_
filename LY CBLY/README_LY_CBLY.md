# LY CBLY — Central Bank of Libya

Scraper for Libya's central bank, **Central Bank of Libya** (cbl.gov.ly), English site.

- **Jira:** DECD-6132 (parent epic DECD-3438 — Regulators 2026 Crawlers)
- **RegCtry:** `LY`
- **RegCode:** `CBLY` (confirmed on the regulators maintenance site)
- **RegulationType:** `Regulated`
- **Script:** `LY CBLY_v_1.ipynb`
- **Output:** `LY CBLY SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`), saved in this folder
- **Run:** plain `requests` + `BeautifulSoup` — no Selenium, the site serves full HTML with no bot protection.

## Lists (ticket ListNr → cbl.gov.ly page)

| ListNr (`ListCode`) | `ListName` (ticket) | `ListLabel` | URL | Ticket comment |
|---|---|---|---|---|
| 1 | Commercial Banks | 1 | https://cbl.gov.ly/en/banks/ | Extract all entities |
| 2 | Representative Offices of Foreign Banks | 1 | https://cbl.gov.ly/en/representative_offices_of_foreign_banks/ | Extract all entities, there are 2 pages in this list |
| 3 | Electronic Payment | 4 | https://cbl.gov.ly/en/electronic-payment/ | NEW LIST! Extract all entities under "Directory of approved electronic payment companies" |

## Site structure / parsing decisions

- All three lists are single HTML `<table>`s (YOOtheme/UIkit theme).
- **`data-filter` attributes** on the `<td>`s of list 1 carry the clean cell value — this also
  bypasses the Cloudflare **email obfuscation** (`[email protected]` in visible text, real address in
  `data-filter`). Fallback for cells without it: visible text minus the hidden mobile label span
  (`span.fs-thead-stacked` — the "Bank:", "Address:" prefixes).
- **List 1 (25 entities):** the "load more" button only *reveals* rows already present in the HTML
  (`tbody.fs-load-more-container`) — a plain GET returns all rows. Columns: Bank → `Name`,
  Address → `Address_1`, Phone, Fax, Email, Website (taken from the cell's `<a href>`).
- **List 2 (18 entities, 2 pages):** paginated via `?sf_paged=N` (`ul.uk-pagination`); the loop
  follows the next-page link until none exists. Columns: Name → `Name`,
  Country (home country of the foreign mother bank) → `Cntry - Mother company` (mapped to ISO-2),
  "Approval Date / CBL" → `RegulationDate` (normalized `%B %d, %Y` → `YYYY-MM-DD`),
  Phone → `Phone`. The "Office Opening Date" column has no sqldict field and is not captured.
  The offices operate in Libya, so `Cntry = LY`.
- **List 3 (13 entities):** the page's only table, under the heading *"Directory of approved
  electronic payment companies"*. Columns: Company name → `Name`, Activity Type → `License_Type`
  (E-Wallet, …), Decision No. → `InternalID_1` (`InternalID_1_type = 'Decision No.'`; one entry
  reads "Agreement", kept verbatim), Decision Date → `RegulationDate` (`DD/MM/YYYY` →
  `YYYY-MM-DD`). "Extension Period" has no sqldict field and is not captured. All entries show
  License Status = `Licensed` (the scraper warns if a different status ever appears).

## Notes

- One list-2 entity is shown in **Arabic on the English page**
  (`مكتب تمثيل البنك المغربي للتجارة الخارجية` — the representative office of Banque Marocaine du
  Commerce Extérieur, Morocco). Name kept verbatim.
- Two list-2 rows (Calyon Bank, Uni Bank) have an **empty Country cell** on the site →
  `Cntry - Mother company` left blank.
- `ListLanguage = EN` (English pages scraped).

## Last run

- 2026-07-13 (v1): **56** entities — 25 Commercial Banks + 18 Representative Offices (2 pages) +
  13 Electronic Payment companies. `LY CBLY SQL Ready 2026-07-13 09.55.36.xlsx`.
