# GH BGH — Bank of Ghana

Jira: [DECD-5022](https://moodysdatapipeline.atlassian.net/browse/DECD-5022) (parent epic DECD-3438)

## Source

Bank of Ghana supervised/registered institution lists, published at `https://www.bog.gov.gh`.
Each list is a **wpDataTables** (WordPress) client-side table. The full list is hidden
behind pagination; selecting **"All"** in the *Show entries* length dropdown reveals every
row in the DOM. Column layout varies by institution type, so extraction is **header-driven**
(`classify()` maps each column header to a sqldict field; e.g. `EMAIL ADDRESS`→Email,
`LOCATION`→Address_1, `REGION`→City, `Regenerated Name of Bureau`→Name).

## Lists (ListCode = Jira ListNr)

| ListCode | ListName | URL slug |
|---|---|---|
| 1  | Banks | registered-institutions/banks |
| 3  | Community Banks | ofisd/list-of-ofis/community-banks |
| 4  | Microfinance Institutions | ofisd/list-of-ofis/microfinance-institutions |
| 6  | Savings and Loans | registered-institutions/savings-loans |
| 7  | Finance Houses | registered-institutions/finance-houses |
| 8  | Leasing Companies | registered-institutions/leasing-companies |
| 9  | Other Banks | registered-institutions/other-banks |
| 10 | Representative Offices in Ghana | registered-institutions/representative-offices |
| 11 | Finance and Leasing Companies | registered-institutions/finance-and-leasing-companies |
| 12 | Mortgage Finance | registered-institutions/mortgage-finance |
| 13 | Remittance Companies | registered-institutions/remittance-companies |
| 14 | Financial NGOs | ofisd/list-of-ofis/financial-ngos |
| 15 | Foreign Exchange Bureaux | ofisd/list-of-ofis/forex-exchange-bureaux |
| 16 | Microcredit Institutions | ofisd/list-of-ofis/micro-credit |

(ListNr 2 and 5 are intentionally absent from the Jira description.)

## Output

`tempfolder/GH BGH SQL Ready <timestamp>.xlsx`, sheet **"SQL Ready"**, project standard `sqldict` schema.

- `RegCtry`=GH, `RegCode`=BGH, `Cntry`=GH, `ListLanguage` not set (source is English).
- `RegulationType`=**Regulated** (all entities are positive — supervised/registered by BoG).
- `ListProcessDate`=run date (`%Y-%m-%d`).

## Run

```
python "GH BGH/GH BGH_v1.py"
```

Requires Chrome + Selenium 4 (driver auto-managed). No login, no anti-bot, no OCR.

## Last run (2026-06-10) — 759 entities

| ListCode | rows |   | ListCode | rows |
|---|---|---|---|---|
| 1 Banks | 23 |  | 11 Finance & Leasing | 3 |
| 3 Community Banks | 147 |  | 12 Mortgage Finance | 1 |
| 4 Microfinance | 132 |  | 13 Remittance | 1 |
| 6 Savings & Loans | 26 |  | 14 Financial NGOs | 12 |
| 7 Finance Houses | 11 |  | 15 Forex Bureaux | 369 |
| 8 Leasing | 2 |  | 16 Microcredit | 27 |
| 9 Other Banks | 1 |  | 10 Rep. Offices | 4 |

Field fill: Name/Address/Phone 100%, Email 97%. City (68%) and Website (8%) only present on
list types that expose Region/Website columns. No encoding issues, no in-list duplicate names.
