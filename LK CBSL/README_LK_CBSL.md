# LK CBSL — Central Bank of Sri Lanka

- **Jira ticket:** DECD-6110
- **Regulator:** Central Bank of Sri Lanka (CBSL)
- **Entry page:** https://www.cbsl.gov.lk/authorized-financial-institutions
- **Script:** `LK_CBSL_v1.ipynb`
- **Output:** `tempfolder/LK CBSL SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`)

## Lists (from Jira)

| ListNr | ListName | Comments |
|---|---|---|
| 1 | Licensed Commercial Banks | |
| 2 | Licensed Finance Companies | |
| 3 | Registered Finance Leasing Establishments | |
| 4 | Licensed Specialised Banks | |
| 5 | Authorised Primary Dealers | NEW LIST! |
| 6 | Authorized Money Broking Companies | NEW LIST! |
| 7 | Licensed Microfinance Institutions | NEW LIST! |

## Section → ListName mapping actually used

The entry page shows seven expandable sections, each linking to a per-category subpage. Section headings match the Jira ListNames, with two slug/wording differences noted below:

| ListCode | Site section heading | Subpage scraped |
|---|---|---|
| 1 | Licensed Commercial Banks | `/authorized-financial-institutions/licensed-commercial-banks` |
| 2 | Licensed Finance Companies | `/authorized-financial-institutions/licensed-finance-companies` |
| 3 | Registered Finance Leasing Establishments | `/authorized-financial-institutions/registered-finance-leasing-establishments` |
| 4 | Licensed Specialised Banks | `/authorized-financial-institutions/licensed-specialised-banks` |
| 5 | Authorised Primary Dealers | `/authorized-financial-institutions/registered-authorised-primary-dealers` (slug says "registered-authorised") |
| 6 | Authorized Money Broking Companies | `/authorized-financial-institutions/authorized-money-broking-companies` |
| 7 | Licensed Microfinance Institutions | `/authorized-financial-institutions/licensed-microfinance-companies` (slug says "companies"; heading on the entry page says "Institutions") |

`ListName` in the output is always the Jira ListName verbatim; `ListCode` = ListNr as string.

## ListLabel

Per ticket owner: 1 = bank named in list name, 2 = insurance, 3 = bank & insurance, 4 = other. Lists 1 (Commercial Banks) and 4 (Specialised Banks) = 1; lists 2, 3, 5, 6, 7 = 4 (`ListLabeldict` in the notebook).

## Approach

- Plain `requests` + `BeautifulSoup` — the pages are static Drupal HTML, no JS rendering needed (no Selenium).
- `verify=False` with `urllib3` InsecureRequestWarning suppressed (the site has had certificate issues), plus a browser User-Agent.
- Each subpage holds one HTML table (`No | Name & Address | Contact Details`). Per row:
  - **Name** = the bold (`<strong>`/`<b>`) segments of the name cell, joined (names are often split across several bold tags, sometimes nested/duplicated — only top-level tags are used). Bold footnotes (containing "Suspended", "Refer Note", "restrained", "w.e.f.", or a bare `*`) are excluded from the name.
  - **Address_1** = the remaining (non-bold) lines of the name cell joined with `", "`. Parenthetical alias/note lines such as `(Formerly Ceylinco Shriram Securities Ltd)` are dropped.
  - **Phone / Fax / Email / Website** come from the two contact columns. When the label lines (`Tel. / Fax / E-mail / Website`) align 1:1 with the value lines, they are mapped by position; otherwise (labels merged on one line, e.g. money brokers) values are classified by pattern (`@` → Email, `www`/`http` → Website, digits → Tel then Fax). `-` placeholders are skipped.
- Fixed fields per row: `RegCtry='LK'`, `RegCode='CBSL'`, `RegulationType='Regulated'`, `ListProcessDate=now (%Y-%m-%d)`.
- After each list the standard `bourange_same_length_array` padding helper is applied; final DataFrame drops empty names and is saved with `to_excel(..., sheet_name='SQL Ready', index=False)` into `tempfolder/`.

## How to run

1. Open `LK_CBSL_v1.ipynb` and run all cells (kernel working directory should be the `LK CBSL` folder; as a `.py` script it resolves its own folder via `__file__`).
2. `tempfolder/` is created/cleaned at start; the xlsx is written there.

Expected volumes (as of 2026-07-09, 132 rows total): 24 commercial banks, 31 finance companies, 47 finance leasing establishments, 6 specialised banks, 12 primary dealers, 8 money brokers, 4 microfinance institutions.

## Caveats

- **List 3 sub-sections:** the finance-leasing page groups entities under bold sub-headers "(A) Licensed Commercial Banks", "(B) Licensed Specialised Banks", "(C) Finance Companies". All of them are Registered Finance Leasing Establishments, so all 47 go under ListCode 3 (many therefore also appear in lists 1/2/4 — expected overlap, not deduplicated).
- **Perpetual Treasuries Limited (list 5)** is kept but carries an on-page note: "Suspended from carrying on the business and activities of a Primary Dealer for a period of 6 months with effect from 4.30 p.m. on 05.07.2026". The note is stripped from Name/Address. Discuss with the team if a suspended dealer should be excluded or flagged differently.
- **Entrust Securities PLC (list 5)** carries the note "Participation in Government Securities Primary Auctions was restrained w.e.f. 24.07.2017" (stripped likewise); its Fax/Email/Website are `-` on the site.
- **Sri Lanka Savings Bank Ltd (list 4)** is marked `*` on the site: "Due to the ongoing merger with NSB, SLBS is presently conducting its operations from NSB premises" — its contact details are NSB's.
- Money-broking companies (list 6) have no Website column on the site, hence Website is empty for list 6.
- Each subpage shows an "As at <date>" validity note (formats vary per page and are inconsistent, e.g. "31st May 2026", "09.07.2026"); not captured into `ListValidityDate`.
- SSL certificate verification is disabled (`verify=False`) because cbsl.gov.lk has had certificate problems.
