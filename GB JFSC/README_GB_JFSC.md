# GB JFSC — Jersey Financial Services Commission

Scraper for the Jersey Financial Services Commission public registers
(<https://www.jerseyfsc.org>). Covers 7 positive (regulated) lists.

- **RegCtry:** GB
- **RegCode:** JFSC
- **RegulationType:** `Regulated` (all rows — these are the regulated registers)
- **Language:** English
- **Notebook:** `GB JFSC_v_1.ipynb`

## Lists

| ListCode | ListName | Source URL |
|---|---|---|
| 1 | Regulated Banks | `…/industry/regulated-entities?lawSectionDC=1&pagesize=10000` |
| 2 | Jersey Funds | `…/industry/sectors/funds/regulated-funds/?pagesize=10000` |
| 3 | Regulated Fund Service Providers | `…/industry/regulated-entities?pagesize=10000&lawSectionFSB=1` |
| 4 | Insurance | `…/industry/regulated-entities?pagesize=10000&lawSectionIns=1` |
| 5 | Regulated Investment Business | `…/industry/regulated-entities?pagesize=10000&lawSectionIB=1` |
| 6 | Regulated Trust Company Business | `…/industry/regulated-entities?pagesize=10000&lawSectionTCB=1` |
| 7 | Money Service Business | `…/industry/regulated-entities?pagesize=10000&lawSectionMSB=1` |

## How it works (the easy way)

The web pages do **not** contain the list HTML — the tables are populated by
JavaScript from two Umbraco JSON APIs. The scraper calls those APIs directly
with `requests` (no Selenium, browser, or OCR), and `PageSize=10000` returns
every row in a single POST.

- **Entities (lists 1, 3–7):** `POST /umbraco/api/RegulatedEntitiesSearch/GetResults`
- **Funds (list 2):** `POST /umbraco/api/RegulatedFundsSearch/GetResults`

Request body:

```json
{"Keyword": "", "PageSize": "10000", "PageNumber": 1,
 "Refiners": [{"Name": "lawSection", "SelectedValue": "<value>"}]}
```

The `lawSection` refiner value selects which entity list is returned (lists 1,
3–7). The funds API takes an empty `Refiners` list.

| ListCode | `lawSection` SelectedValue |
|---|---|
| 1 | `bankingdc` |
| 2 | *(none — funds API)* |
| 3 | `fundservicesbusinessfsb` |
| 4 | `ibacomposite,ibageneral,ibalongterm,ibbcomposite,ibbgeneral,ibblongterm` |
| 5 | `investmentbusinessib` |
| 6 | `trustcompanybusinesstcb` |
| 7 | `moneyservicebusinessmsb` |

Each API result item provides `Title` (name), `Url` (detail page ending in the
JFSC reference id) and a `Properties` list. For entities the relevant property
is `LawSection` (the licences held); for funds it is `FundType`.

## Field mapping

| sqldict field | Source |
|---|---|
| `Name` | `Title` (trimmed) |
| `InternalID_1` | trailing numeric id from `Url` (the JFSC entity/fund reference) |
| `InternalID_1_type` | `JFSC Reference` |
| `License_Type` | `LawSection` (entities) / `FundType` (funds) |
| `RegulationType` | `Regulated` |
| `RegCtry` / `RegCode` / `ListCode` | `GB` / `JFSC` / `1`–`7` |
| `ListName` | per table above |
| `ListProcessDate` | run date (`%Y-%m-%d`) |

## Run

```powershell
cd "GB JFSC"
jupyter nbconvert --to notebook --execute --inplace "GB JFSC_v_1.ipynb"
```

Output: `GB JFSC SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`) in this folder.

## Expected volume (run 2026-06-15)

| ListCode | Rows |
|---|---|
| 1 Regulated Banks | 19 |
| 2 Jersey Funds | 597 |
| 3 Regulated Fund Service Providers | 461 |
| 4 Insurance | 168 |
| 5 Regulated Investment Business | 68 |
| 6 Regulated Trust Company Business | 761 |
| 7 Money Service Business | 24 |
| **Total** | **2,098** |

Counts match the "X results" header shown on each live page. If a future run
returns 0 for any list, check that the `lawSection` SelectedValue still matches
the site's filter checkbox `value` attribute (read it from the page's
`input[type=checkbox][name=refiner]` elements).
