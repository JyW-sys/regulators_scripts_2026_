# SC CBSEY

## Regulator Information

- **Country/Region Code**: SC
- **Regulator Code**: CBSEY
- **Full Name**: Central Bank of Seychelles
- **Website**: https://www.cbs.sc/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6296

## Script

- **Current Version**: `SC_CBSEY_v1.py`
- **Approach**: The public pages under `cbs.sc/Financial/*.html` are an AngularJS app that renders data from a JSON endpoint. The scraper calls that endpoint directly with `requests` (no browser, no "click next" needed — the API returns the full list per type). `verify=False` for the corporate TLS proxy.

## Data source (JSON API)

`https://www.cbs.sc/Controller/getFinancialInstitution.jsp?type=<TYPE>` → returns `{ "<key>": [ {record}, ... ] }`.

Record fields: `institutionName, streetName, poBox, city, state, country, telephone, email, website, status`.

## List Types → API mapping

| ListNr | ListName | API `type` | ListLabel | Count |
|--------|----------|------------|-----------|-------|
| 1 | Commercial Banks | `bank institution` | 1 | 7 |
| 2 | Non-bank Credit Institutions | `NBCI` | 4 | 2 |
| 3 | Bureaux de Change | `bdc class A` + `bdc class B` | 4 | 21 |
| 4 | Financial Leasing | `DTI` + `NDTI` | 4 | 2 |
| 5 | Payment Service Providers | `PSP` | 4 | 4 |
| 6 | Credit Unions | `NBDTI` | 4 | 1 |
| | | | **Total** | **37** |

- List 3 merges the two ticket URLs (`BureaudeChange.html` = class A, `BureaudeChange1.html` = class B).
- List 4 merges the two ticket URLs (`DepositInstitution.html` = DTI, `NonDepositInstitution.html` = NDTI).
- List 6 "Credit Unions" maps to API type `NBDTI` (returns "Seychelles Credit Union").

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | `institutionName` (leading `"N. "` numbering stripped) |
| Address_1 | `streetName` |
| Address_2 | `poBox` + `state` |
| City | `city` |
| Phone | `telephone` |
| Email | `email` |
| Website | `website` |
| Cntry | `SC` |
| RegulationType | `Regulated` |
| ListName | per table above |
| ListLabel | 1 for Commercial Banks, else 4 |
| RegCtry / RegCode / ListCode | SC / CBSEY / ListNr |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **37 entities total.** Counts are small but complete (this is a small jurisdiction).
- Only list 1 (Commercial Banks) is labelled as a bank list (ListLabel 1); the rest are non-bank financial → 4. No insurance lists in this ticket.
- API types `NPS` (0 records) and `Operator` (payment-system operator) exist but are not part of the 6 requested lists, so they are excluded.
