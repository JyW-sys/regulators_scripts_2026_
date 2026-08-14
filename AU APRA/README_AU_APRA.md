# AU APRA

## Regulator Information

- **Country/Region Code**: AU
- **Regulator Code**: APRA
- **Full Name**: Australian Prudential Regulation Authority
- **Website**: https://www.apra.gov.au/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6743

## Script

- **Current Version**: `AU_APRA_v3.py` (supersedes `AU_APRA_v2.ipynb`)
- **Approach**: `requests` + `BeautifulSoup` over six accordion pages, plus two
  extra pages (private health insurers, superannuation). The superannuation
  workbook is an ordinary `.xlsx` link on its page and is read straight into
  `pandas` from memory. `verify=False` for the corporate TLS proxy.
- **No browser.** v2 drove Selenium purely to download the superannuation
  workbook; v3 fetches it with `requests`, so there is no Chrome dependency,
  no download-folder race and no `wait_for_file()`.

### Why v3 exists

v2 **ran to completion** — that is what made it dangerous. Three of its defects
were silent, producing a full-looking file with wrong values:

1. **Typology was the wrong string on almost every row.** `parse_tables()` did
   `typology = p.get_text() if p else h2.get_text()`, preferring `<p>` over
   `<h2>`. On these pages the section heading *is* the `<h2>` and the first
   `<p>` is the **first company name inside the table**, so all 67 Australian-owned
   ADIs were stamped `Alex Bank Pty Ltd` as their section. v3 tries `h2`/`h3`
   first and keeps `<p>` only as a fallback — which is still needed, because the
   NOHC page genuinely has no heading tag and carries its three section titles
   in `<p>` (measured).
2. **List 11 never fetched its own page.** The `AU_APRA_11` branch read `soup`,
   a leftover variable from the `AU_APRA_7` iteration, so it re-parsed the
   life-insurance table instead of Retirement Savings Accounts.
3. **List 12 shifted a column.** v2 appended field-by-field inside the row loop
   and called `bourange_same_length_array()` **once, after all 28 cards**. 9 of
   the 28 private health insurers publish no Email row, so every Email after the
   first gap was written against the wrong insurer. v3 collects a whole card
   into a dict and appends once per card.

Other v3 changes:

- **ListNr 8 dropped** — a duplicate of ListNr 5 in the ticket (same register of
  non-operating holding companies). Confirmed with the user 2026-08-13.
- Names are read from the cell's first `<p>` with the embedded PDF "download
  tile" stripped first. v2 did `name.split(':')[0]`, which left the name
  duplicated (`Alex Bank Pty Ltd Alex Bank Pty Ltd`).
- **Unknown section headings raise a loud warning** and are skipped rather than
  silently mis-filed, so a site re-heading cannot corrupt the output.
- `scriptfolder` resolved per project convention (no hard-coded `C:\` path).
- Non-schema `'Check'` column dropped from `sqldict`.
- New data captured that v2 dropped: revocation / deregistration dates →
  `CancellationDate`, RSA approval date → `RegulationDate`, RFC category and
  ABN, private-health membership type and restriction, RSE fund status.

### Page structure

Two accordion markups are in use and both are handled: older pages wrap each
section in `div.js-accordion`; the registered-financial-corporations page uses
`div.anx-accordion__item` with an `<h3>`. Dispatch is by **section heading text**
through the `SECTIONS` map, not by position, so a re-ordered accordion cannot
silently mis-file rows.

## List Types

`ListLabel` is left blank on these lists — they are pre-existing and colleagues
fill the label manually downstream (user decision, 2026-08-13). No new list was
added in v3, so no label had to be set here.

| ListNr | ListName | Source page |
|--------|----------|-------------|
| 1 | List of Authorised Deposit-taking Institutions | `/register-authorised-deposit-taking-institutions` |
| 2 | List of Register of general insurance | `/register-general-insurance` |
| 3 | Insurers Only Authorised to Conduct Run-Off Business | `/register-general-insurance` |
| 4 | Insurers that have had Insurance Authorisations Revoked (since 1st January 2002) | `/register-general-insurance` |
| 4 | Insurers deregistered under the Corporations Act 2001 | `/register-general-insurance` |
| 5 | Register of non-operating holding companies (NOHCs) | `/register-non-operating-holding-companies` |
| 6 | List of Registers of life insurance companies | `/list-of-registered-life-insurers-and-friendly-societies` |
| 7 | List of Friendly Societies | `/list-of-registered-life-insurers-and-friendly-societies` |
| ~~8~~ | ~~duplicate of 5~~ | **dropped** |
| 9 | List of RSEs | `/list-of-superannuation-institutions` (xlsx, sheet `List of RSE`) |
| 10 | List of RSE Licensees | `/list-of-superannuation-institutions` (xlsx, sheet `List of Licensee`) |
| 11 | List of Institutions offering Retirement Savings Accounts | `/list-institutions-offering-retirement-savings-accounts` |
| 12 | List of Register of private health insurers | `/list-of-registered-private-health-insurers` |
| 13 | List of Registered financial corporations | `/list-of-registered-financial-corporations` |

Base: `https://www.apra.gov.au`

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | first `<p>` of the row's first cell, PDF download tile stripped |
| Typology | accordion **section heading** (`h2`/`h3`, `<p>` fallback); for list 9 the Fund Type; for list 12 the membership type |
| CoType | RSE Fund Status (list 9) |
| License_Type | run-off commencement (list 3), Class of Licence (list 10), restriction (list 12) |
| InternalID_1 / _type | ABN (list 13) / Fund ABN (9) / Trustee ABN (10) / licence number where published |
| InternalID_2 / _type | Registration Number (9) / Licence Number (10) |
| Address_1 / City / Zip | Postal Address from the workbook or the insurer card; City and Zip split off by `split_au_address()` (walks backwards past state + 4-digit postcode to the suburb) |
| Phone / Fax / Email / Website | insurer card (list 12) and workbook contact columns (list 9) |
| RegulationDate | "Date Approved" column, where the table has one (list 11) |
| CancellationDate | revocation / deregistration date column (list 4) |
| Name - Mother Company | Trustee Name (list 9) |
| Cntry / RegCtry / RegCode | `AU` / `AU` / `APRA` |
| ListLanguage | `EN` |
| RegulationType | per section — see below |
| ListProcessDate | run date (`%Y-%m-%d`) |

### RegulationType by section

`Regulated` everywhere except the two list-4 sections: revoked authorisations →
`Revoked`, deregistered under the Corporations Act → `Deregistered`. List 9 rows
whose Fund Status contains "wound up" → `Wound Up`.

## Status / QA

- **Output**: `AU APRA SQL Ready 2026-08-13 12.18.46.xlsx`, **1700 rows**,
  fixed 43-column schema, sheet `SQL Ready`.

| ListNr | ListName | RegulationType | rows |
|--------|----------|----------------|------|
| 1 | List of Authorised Deposit-taking Institutions | Regulated | 126 |
| 2 | List of Register of general insurance | Regulated | 79 |
| 3 | Insurers Only Authorised to Conduct Run-Off Business | Regulated | 10 |
| 4 | Insurers that have had Insurance Authorisations Revoked | Revoked | 115 |
| 4 | Insurers deregistered under the Corporations Act 2001 | Deregistered | 2 |
| 5 | Register of non-operating holding companies (NOHCs) | Regulated | 31 |
| 6 | List of Registers of life insurance companies | Regulated | 22 |
| 7 | List of Friendly Societies | Regulated | 10 |
| 9 | List of RSEs | Regulated | 647 |
| 10 | List of RSE Licensees | Regulated | 53 |
| 11 | List of Institutions offering Retirement Savings Accounts | Regulated | 7 |
| 12 | List of Register of private health insurers | Regulated | 28 |
| 13 | List of Registered financial corporations | Regulated | 570 |
| | **Total** | | **1700** |

- Every one of these counts was checked against the live page before the run.
  List 5 breaks down as 8 Banking Act s11AA(2) / 17 Insurance Act s18 /
  6 Life Insurance Act s28A = 31, matching the three `<p>` sections.
- **Zero unknown section headings** — every table on all six accordion pages
  resolved through `SECTIONS`.
- **Typology** 1647/1700 non-empty (the 53 blanks are list 10, which has no
  section concept), and every value is one of the `SECTIONS` keys — i.e. the v2
  company-name-as-typology defect is gone.
- **List 12 Email = 19/28**, matching the 9 insurers that publish no email;
  spot-checked that each email now sits on its own insurer.
- Fill rates: Name 1700/1700, Cntry 1700/1700, InternalID_1 1222/1700,
  Address_1 728/1700, City 725/1700, Zip 727/1700, Phone 673/1700,
  CancellationDate 117/1700 (= the 115 revoked + 2 deregistered).
- `RegulationType` and `ListProcessDate` non-empty on all 1700 rows.

### Items needing your confirmation

1. **ListNr 8 is not produced** — treated as a ticket duplicate of ListNr 5.
   Confirmed verbally; noting it here so it is visible at review time.
2. **`RegulationType` values `Revoked` / `Deregistered` / `Wound Up`** —
   CLAUDE.md says non-`Regulated` cases are decided case by case. Confirm these
   three strings are what BVD wants.
3. **`ListLabel` left blank** on all 13 lists, per your instruction that
   colleagues fill it manually. Say the word if you want it populated
   (1 = bank, 2 = insurance, 3 = both, 4 = other).
4. **Lists 9 / 10 come from the superannuation workbook**, so their vintage is
   the workbook's publication date, not the run date.

### Environment notes

- Global Python environment; `requests`, `beautifulsoup4`, `pandas`, `openpyxl`.
  No Selenium, no ChromeDriver.
- `verify=False` + `urllib3.disable_warnings` are required behind the corporate
  TLS proxy.
