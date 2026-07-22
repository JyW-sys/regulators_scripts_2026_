# TJ NBTAJ

## Regulator Information

- **Country/Region Code**: TJ
- **Regulator Code**: NBTAJ
- **Full Name**: National Bank of Tajikistan
- **Website**: https://www.nbt.tj/en/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6295

## Script

- **Current Version**: `TJ_NBTAJ_v1.py`
- **Approach**: Static HTML, `requests` + `BeautifulSoup` (no browser needed). `verify=False` for the corporate TLS proxy; desktop User-Agent. All 6 lists scraped into one output file.

## List Types

| ListNr | ListName | URL | ListLabel |
|--------|----------|-----|-----------|
| 1 | Banks | https://www.nbt.tj/en/banking_system/banks.php | 1 |
| 2 | Micro Credit Deposit Organizations | https://www.nbt.tj/en/banking_system/tashkilot_amonatii_karzii_khurd.php | 4 |
| 3 | Micro-Loan Organizations | https://www.nbt.tj/en/banking_system/tashkilot_karzii_khurd.php | 4 |
| 4 | Micro Loan Funds | https://www.nbt.tj/en/banking_system/fondhoi_karzii_khurd.php | 4 |
| 5 | List of representative offices of foreign banks | https://www.nbt.tj/en/banking_system/namoyandagi-bonkho/rui_nam_bonk_horigi.php | 1 |
| 6 | List of professional participants of the insurance market | https://www.nbt.tj/en/sugurta/insurance_companies.php | 2 |

## Page structure

Every list is a single `<table>` where each entity is a **rowspan block**: a leading numbered cell + a name cell (both carry `rowspan`), followed by `label | value` rows. Labels seen: `Chairman/Board Chairman/Director/General Director/(Acting) ...`, `(Acting) Chief Accountant`, `Address`, `Telephone`/`Phone`, `Fax`, `Website`, `Email`/`E-mail`.

- On lists 1-5 the number/name cells are `<td>`; on list 6 (insurance) they are `<th>`. Detection is by the presence of a `rowspan` on the first cell of a row, so both are handled the same way.
- Labels on lists 1-5 end with `:`; on list 6 they do not. The parser strips a trailing `:` and lower-cases before matching.
- Officer rows (chairman / director / chief accountant) are intentionally ignored — there is no sqldict field for them.
- `-` placeholder values are treated as empty.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | entity name cell (rowspan) |
| Address_1 | `Address` value (full address string) |
| Phone | `Telephone` / `Phone` value |
| Fax | `Fax` value (only lists 1 & 6 supply it) |
| Website | `Website` value (link href as fallback) |
| Email | `Email` / `E-mail` value (`mailto:` stripped) |
| Cntry | `TJ` |
| RegulationType | `Regulated` |
| ListName | exact ListName above |
| ListLabel | per list (see table) |
| ListLanguage | `EN` (English `/en/` pages) |
| RegCtry / RegCode / ListCode | `TJ` / `NBTAJ` / `<ListNr>` |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Counts / QA

| ListNr | ListName | Entities |
|--------|----------|----------|
| 1 | Banks | 19 |
| 2 | Micro Credit Deposit Organizations | 27 |
| 3 | Micro-Loan Organizations | 2 |
| 4 | Micro Loan Funds | 21 |
| 5 | List of representative offices of foreign banks | 1 |
| 6 | List of professional participants of the insurance market | 16 |
| **Total** | | **86** |

## Notes / QA

- **86 entities**, no blank names, no duplicates within any list.
- Field fill rates: Name 86/86, Address_1 86/86, Phone 85/86, Website 62/86, Email 80/86, Fax 13/86.
- The single missing phone (`CJSC "Freedom Bank Tajikistan"`) is genuinely blank on the source page (empty `Telephone:` cell), not a parse miss.
- **City / Zip left blank**: the site publishes only a single combined address string (and the city sits at the *start* of the address on lists 1-5 but at the *end* on list 6), so there is no reliable discrete City field to extract. Full address is kept in `Address_1`. Raise if BVD wants City split out.
- **CoType / InternalID / License_Type left blank**: the pages expose no licence/registration number or company-type field.
- **ListLabel decisions**: list 1 (Banks) and list 5 (representative offices of foreign banks) → `1` (bank); list 6 (insurance market participants) → `2` (insurance); lists 2-4 (micro-credit-deposit / micro-loan / micro-loan-fund, i.e. non-bank microfinance) → `4` (everything else). Confirm list 5 treatment if a foreign-bank representative office should not count as a bank list.
