# KH NBC

## Regulator Information

- **Country/Region Code**: KH
- **Regulator Code**: NBC
- **Full Name**: National Bank of Cambodia
- **Website**: https://www.nbc.gov.kh/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6366

## Script

- **Current Version**: `KH_NBC_v1.py`
- **Approach**: each of the 9 lists lives on its own `nbc.gov.kh/english/supervision/<slug>.php` page. All 9 English pages returned plain HTTP 200 to `requests` with a desktop User-Agent (no Cloudflare/WAF challenge, no DrissionPage needed). Each page has a small "FILENAME / FORMAT / UPDATED" table with a single PDF download link (the "PDF icon under FORMAT" from the Jira Comments); the scraper resolves that link, downloads the PDF into `tempfolder/`, and parses it with **pdfplumber**.
- **Language**: the NBC publishes the English-language mirror of the site under `/english/...`, which was used directly — no separate translation step was needed for the page/URL. The underlying **PDF files themselves are bilingual** (Khmer + English per entity); see parsing notes below for how the English text is isolated.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Commercial Banks | https://www.nbc.gov.kh/english/supervision/commercial_banks.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 2 | Specialized Banks | https://www.nbc.gov.kh/english/supervision/specialized_banks.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 3 | Microfinance Non Deposit Taking Institutions | https://www.nbc.gov.kh/english/supervision/microfinance_non_deposit_taking_institutions.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 4 | Microfinance Deposit Taking Institutions | https://www.nbc.gov.kh/english/supervision/microfinance_deposit_taking_institutions.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 5 | Representative Offices | https://www.nbc.gov.kh/english/supervision/representative_offices.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 6 | Financial Leasing Companies | https://www.nbc.gov.kh/english/supervision/leasing_companies.php | Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 7 | Payment Service Institutions | https://www.nbc.gov.kh/english/supervision/payment_service.php | NEW LIST! Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 8 | Credit Bureau Companies | https://www.nbc.gov.kh/english/supervision/credit_bureau_companies.php | NEW LIST! Click on the PDF icon under FORMAT, download and extract the English line of all entities |
| 9 | Rural Credit Institutions | https://www.nbc.gov.kh/english/supervision/rural_credit_institutions.php | NEW LIST! Click on the PDF icon under FORMAT, download and extract the English line of all entities |

## Page structure & parsing

Each PDF is a single 4-column table: `No. | Name | Address | Contact`, generated from a bilingual register (Khmer script first, English translation for the same entity following). The Khmer/English pairing is **not laid out consistently** across the 9 files:

- In some files (e.g. `Commercial_Banks.pdf`, `Specialized_Banks.pdf`) an entity spans **two physical table rows** — the first row (with the numeric `No.`) holds the Khmer name/address plus the Contact phone; the second row (`No.` cell blank) holds the English name/address.
- In others (e.g. `MDIs.pdf`, `Leasing_Institutions.pdf`, `PSIs.pdf`, `CBC.pdf`) Khmer and English text for the same field are stacked with a literal newline **inside a single cell**, so the whole entity is one physical row.
- A few files mix both patterns entity-to-entity within the same PDF (e.g. `RCIs.pdf`).

Rather than hard-code a layout per file, the parser (`parse_pdf()`) groups table rows into per-entity blocks — a new block starts whenever the `No.` column is a bare integer, and a blank-`No.` row is treated as a continuation of the current block — then classifies every text line in the block as Khmer or English by checking for Khmer-Unicode-block codepoints (U+1780–U+17FF). Only non-Khmer lines are kept for `Name`/`Address_1` (per the Jira Comments instruction to "extract the English line"); `Contact` is language-neutral digits, so all lines are kept and joined with `; ` (some entities list 2+ phone numbers).

Every PDF's title block also states an explicit "As at DD Month YYYY" line — extracted via regex into `ListValidityDate` (all 9 lists show **2026-05-31** as of this run).

`City` is derived from the tail of the English address: matched against a static list of Cambodian city/province names, falling back to the last comma-separated segment. A handful of Payment Service Institution addresses end in a trailing country name (`", Cambodia"` / `", Kingdom of Cambodia"`) rather than a city — that suffix is stripped first so `City` reflects the actual city/province, not the country.

Numbering was verified contiguous (`1..N`, no gaps/resets/duplicates) in all 9 PDFs, and every parsed entity yielded a non-empty English name — no rows needed to be dropped for a missing `Name`.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | English line of the entity's Name column |
| License_Type | the Jira `ListName` for that ListNr (each PDF is single-category) |
| Address_1 | English line(s) of the entity's Address column |
| City | derived from the tail of `Address_1` (city/province match, country suffix stripped) |
| Phone | entity's Contact column, all lines joined with `; ` |
| Cntry | `KH` |
| RegulationType | `Regulated` |
| ListValidityDate | the PDF's own "As at DD Month YYYY" title line, parsed to ISO |
| ListLanguage | `EN` |
| RegCtry / RegCode | `KH` / `NBC` |
| ListCode / ListName | Jira ListNr / Jira ListName (verbatim) |
| ListLabel | see judgment calls below |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

**Row counts per list** (287 total):

| ListNr | ListName | Rows |
|---|---|---|
| 1 | Commercial Banks | 58 |
| 2 | Specialized Banks | 7 |
| 3 | Microfinance Non Deposit Taking Institutions | 85 |
| 4 | Microfinance Deposit Taking Institutions | 3 |
| 5 | Representative Offices | 5 |
| 6 | Financial Leasing Companies | 12 |
| 7 | Payment Service Institutions | 28 |
| 8 | Credit Bureau Companies | 1 |
| 9 | Rural Credit Institutions | 88 |

- **Non-empty rates**: Name/Cntry/Address_1/Phone/City/License_Type/ListValidityDate = 100% across all 287 rows. `Website`/`Email` are 0% — none of the 9 PDFs publish a website or email column for entities, so this is a genuine source gap, not a parsing gap.
- **Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` — zero hits across all columns.
- **Khmer leftover check**: zero rows with residual Khmer-script characters in `Name`/`Address_1` — the language classifier cleanly isolated the English lines in every file.
- **Duplicate `Name` check**: zero duplicates across all 287 rows (each of the 9 lists is disjoint by license category, and no entity repeats within a list).
- **City spelling**: the source PDFs themselves are not internally consistent on spelling/spacing (e.g. `Phnom Penh` vs `PhnomPenh` vs `Phnom Penh City`; `Kampot Province` vs `Kompot Province`) — these are reproduced as published rather than normalized, since the underlying `Address_1` also carries the same source spelling.
- **ListLabel judgment calls** (1 = bank, 2 = insurance, 3 = both, 4 = everything else):
  - Lists 1 (Commercial Banks) and 2 (Specialized Banks) → `1`.
  - List 5 (Representative Offices) → `1`, because every entity name is explicitly "Representative office of [a named bank]" (e.g. Standard Chartered, foreign commercial banks) — these are all bank representative offices, consistent with the `KE CBK` precedent (`Representative Offices of Foreign Banks` → 1).
  - Lists 3 and 4 (Microfinance Non-Deposit-Taking / Deposit-Taking Institutions) → `4`. Neither list is literally named "Bank"; this follows the same precedent set in `TJ NBTAJ` (non-bank microfinance, including deposit-taking microfinance, classified as 4 rather than 1). Flagged here since MDIs (list 4) do take deposits and are prudentially supervised similarly to banks under Cambodian law — a reviewer may want to reconsider this specific list as `1` if the project's definition of "bank list" is meant to include deposit-taking microfinance.
  - Lists 6 (Financial Leasing), 7 (Payment Service Institutions), 8 (Credit Bureau Companies), 9 (Rural Credit Institutions) → `4` (none are banks or insurers).
- **No blocked/skipped lists** — all 9 pages and PDFs were reachable via plain `requests` (verify=False, desktop User-Agent); DrissionPage fallback was not needed for this regulator.
- No baseline exists yet in `qa_positive_combined/` for this regulator (new/greenfield folder).
