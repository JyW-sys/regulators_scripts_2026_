# KG NBKR Regulatory Lists

Source: Jira DECD-6107 — National Bank of the Kyrgyz Republic (NBKR).

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| KG | NBKR | 1 | List of commercial banks of the Kyrgyz Republic | https://www.nbkr.kg/index1.jsp?item=71&lang=ENG | Extract all entities from the list "List of commercial banks of the Kyrgyz Republic and number of their branches". The page holds several other tables (register of licenses, Islamic-banking register, representative offices, banks in liquidation/conservation) — those are skipped. |

## Approach

- Static page, no JS rendering needed: plain `requests` (browser User-Agent, `verify=False` with the urllib3 InsecureRequestWarning suppressed) + BeautifulSoup/lxml.
- The page contains six tables. The scraper anchors on the heading text `List of commercial banks of the Kyrgyz Republic and number of their branches ...` and takes the first `<table>` after it (`heading.find_next('table')`), so the other lists on the page are never picked up. It raises a clear error if the heading or table disappears.
- Target table columns: `N | Full name of the bank | Abbreviated name | Mail Address, phone number | Chairman | Number of branches | e-mail, Web-site`.
  - `Name` = "Full name of the bank". The branch count is a separate column and is NOT appended to the name and NOT treated as an entity.
  - The combined address cell is split into `Zip` (leading postal code), `City` (all rows are Bishkek), `Address_1` (street part), `Phone` (`ph:`/`Ph.` values) and `Fax` (one bank shows a `fax:` value).
  - The e-mail/web cell is split into `Email` (all e-mails, comma-joined) and `Website`.
  - Chairman name and branch count columns are not mapped (no matching sqldict field).
- Constants per row: `RegCtry='KG'`, `RegCode='NBKR'`, `ListCode='1'`, `ListName='List of commercial banks of the Kyrgyz Republic'` (Jira wording, without the "as of <date>" suffix), `RegulationType='Regulated'`, `ListProcessDate=now (%Y-%m-%d)`.
- No license numbers appear in this table (they live in the separate "Register of licenses" list, out of scope), so `InternalID_1` stays empty.

## How to run

Open `KG_NBKR_v1.ipynb` and run all cells (global/venv Python with `requests`, `bs4`, `lxml`, `pandas`, `openpyxl`). The script:

1. Resolves `scriptfolder` (`__file__` when run as .py, `os.getcwd()` in a notebook) and creates/cleans `tempfolder/`.
2. Scrapes the target table and fills the mandatory `sqldict`.
3. Writes `KG NBKR SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`) into `tempfolder/`.

Last verified run (2026-07-09): 26 banks, 100% coverage on Name/Address_1/City/Zip/Email/Website, 88.5% Phone, 3.8% Fax.

## Caveats

- The English page mixes visually-identical Cyrillic letters into Latin words (e.g. `Оpen`, `Сompany`, `Тhe oреn ... соmраnу«Kylym Bank»`). The scraper maps these homoglyphs back to Latin in Name/Zip/City/Address so downstream matching is not broken.
- One zip is `C0082` (Mbank) — that is what the source shows (likely a typo for a 720xxx code); kept as-is after homoglyph fix.
- The heading carries a validity date ("as of 3 July 2026") that changes over time, so the anchor regex only matches the stable part of the heading.
- Three newer banks (Alma Finance Bank, Asman Bank, Muras Bank) list no phone number on the source page; only one bank (FinanceCreditBank) lists a fax.
