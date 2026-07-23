# LS CBLE — Central Bank of Lesotho

- **Jira ticket:** DECD-6112
- **Regulator:** Central Bank of Lesotho (CBL)
- **Website:** https://centralbank.org.ls (WordPress, listings served by the wpbdp Business Directory plugin)
- **Script:** `LS_CBLE_v1.ipynb`
- **Output:** `tempfolder/LS CBLE SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`)

## Lists

| ListNr | ListName | URL |
|---|---|---|
| 1 | Commercial Banks and Forex Agencies | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/commercial-banks-and-forex-agencies/ |
| 2 | Insurance Brokers | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/insurance-brokers/ |
| 3 | Micro Finance Institutions | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/micro-finance-institutions/ |
| 4 | Insurance Companies | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/insurance-companies/ |
| 5 | Asset Managers in Lesotho | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/asset-managers-in-lesotho/ |
| 6 | Credit Bureaus | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/credit-bureau/ (NEW LIST) |
| 7 | Foreign Exchange Bureau and Money Transfer | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/foreign-exchange-bureau-and-money-transfere/ (NEW LIST) |
| 8 | Pension Fund Administrators | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/pension-fund-administrators/ (NEW LIST) |
| 9 | Pension Funds | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/pension-fund/ (NEW LIST) |
| 10 | Mobile Money Issuers | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/mobile-money-issuers-in-lesotho/ (NEW LIST) |
| 11 | Pension Fund Intermediaries | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/pension-fund-intermediaries/ (NEW LIST) |
| 12 | Stock Brokers | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/stock-brokers/ (NEW LIST) |
| 13 | Trustees | https://centralbank.org.ls/other-financial-institutions-2/wpbdp_category/trustees/ (NEW LIST) |

## ListLabel

Per ticket owner: 1 = bank named in list name, 2 = insurance, 3 = bank & insurance, 4 = other. List 1 (Commercial Banks and Forex Agencies) = 1; lists 2 and 4 (Insurance Brokers / Insurance Companies) = 2; all other lists = 4 (`ListLabeldict` in the notebook).

## Approach

- Pure `requests` + `BeautifulSoup` (no Selenium needed): all category pages are static HTML and respond normally to a browser `User-Agent`. `verify=False` is used and `urllib3` InsecureRequestWarning is suppressed.
- Each category page shows listing cards (`div.wpbdp-listing`). Per card the scraper extracts:
  - **Name** — `div.listing-title h3`
  - **Phone** — `div.wpbdp-field-phone .value`
  - **Address_1** — the value `div` inside `div.address-info`
  - Cards also show a "Name of CEO or Managing Director" field, which has no matching sqldict column and is not extracted. Email / Website / City are not published on the cards (detail pages carry no extra fields either, so detail pages are not fetched).
- **Pagination:** wpbdp paginates 10 cards per page using `/page/N/` URLs. The scraper follows the `.wpbdp-pagination .next a` ("Next →") link until it disappears (safety cap 60 pages, 1 s delay between requests). Categories with a single page have an empty pagination block. As of 2026-07-09: List 2 = 6 pages, List 3 = 16 pages, List 9 = 2 pages, all others 1 page.
- Listing card IDs (`wpbdp-listing-NNNN`) are tracked per category to guard against pagination overlap (none observed).
- Fixed fields per row: `RegCtry='LS'`, `RegCode='CBLE'`, `ListCode='1'…'13'`, `ListName` per the table above, `RegulationType='Regulated'`, `ListProcessDate=YYYY-MM-DD` of the run.
- After each list, `bourange_same_length_array` pads the sqldict; the final DataFrame drops empty names and is saved as `LS CBLE SQL Ready <timestamp>.xlsx` into `tempfolder/` (sheet `SQL Ready`).

## How to run

1. Open `LS_CBLE_v1.ipynb` and run all cells (or export the code cells to a `.py` and run it — `scriptfolder` resolves via `__file__` with an `os.getcwd()` fallback for notebooks).
2. Requirements: `requests`, `beautifulsoup4`, `lxml`, `pandas`, `openpyxl`. No browser driver, no OCR.
3. `tempfolder/` is created/emptied at the start of every run; the output xlsx is written there.

## Caveats / site quirks

- **Duplicate listing posts on the site:** the Micro Finance Institutions category contains two entities published twice with `-2` slugs (`atlas-finance-pty-ltd` / `atlas-finance-pty-ltd-2`, `boikaho-financial-services` / `boikaho-financial-services-2`). These are site data-entry duplicates, not pagination overlap; the writer cell drops duplicates on `(ListCode, Name, Address_1)` keeping the first (159 scraped → 157 kept for List 3).
- **Test listing:** the Insurance Brokers category contains a bare admin test entry named "Test New" (no CEO, phone or address). It is explicitly dropped in the writer cell (52 scraped → 51 kept for List 2).
- **List 8 (Pension Fund Administrators) has no addresses:** the 4 cards in that category carry only Name / CEO / Phone; their detail pages also have no address field, so `Address_1` is empty for those rows.
- Small lists are genuine: Credit Bureaus (List 6) and Trustees (List 13) each contain exactly 1 entity on the site; Foreign Exchange Bureau and Money Transfer (List 7) contains 2. Verified manually — pages return the listings shown, no further pages exist (e.g. `/page/2/` returns 404).
- Lists 4 and 12 have exactly 10 entities (= one full page); `/page/2/` was manually confirmed to 404, so no records are being missed at the page boundary.
- A few rows lack Phone (Green Point Brokers in List 2, Goldenheart Financial Services in List 3) — those fields are simply absent on the site.

## Last verified run (2026-07-09)

269 rows total: 4 / 51 / 157 / 10 / 6 / 1 / 2 / 4 / 12 / 5 / 6 / 10 / 1 for ListCodes 1–13. Name filled 100%, Address_1 98.5%, Phone 99.3%, no duplicates, no mojibake.
