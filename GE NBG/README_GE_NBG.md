# GE NBG Regulatory Lists

National Bank of Georgia (NBG) — Georgia's central bank and integrated financial regulator. The site (`nbg.gov.ge`) is a **Next.js** application, so entity data is available as JSON without rendering the page. Three source mechanisms are used — **no Selenium/OCR required**:

1. **JSON API** — `https://nbg.gov.ge/gw/api/pg/pages/static/<key>/organizations`. Used by every list except the Excel registers and L13. **Send header `Accept-Language: en`** or the `title` field comes back null/Georgian. This is the *deterministic* English source. (The page-embedded `__NEXT_DATA__` was avoided: its server-side render returns `title` in Georgian intermittently — that is what caused L1/L2 to come out Georgian in an earlier run.)
2. **Excel registers** — linked on the non-bank-institutions page; resolved at runtime by their English anchor text (filenames are date-stamped, so they must not be hardcoded).
3. **Content table** — a few tabs publish their entities as an HTML `<table>` inside the `content/details` endpoint's `description` field instead of via `/organizations` (Specialized Depositaries). Parsed with BeautifulSoup. The `/organizations` endpoint for that key returns empty, so it must be read from `content/details`.

As a safety net, any entity `Name` that still contains Georgian script (Unicode block U+10A0–U+10FF) is translated to English via the `gtx` endpoint, so an intermittent non-English API response can never reach the output.

Jira: [DECD-4822](https://moodysdatapipeline.atlassian.net/browse/DECD-4822) · `RegCtry=GE`, `RegCode=NBG`, all entities `RegulationType=Regulated`.

| ListCode | ListName | Source | Key / sheet | Rows |
|---|---|---|---|---|
| 1 | Licensed Commercial Banks | API | `licensedCommercialBanks` | 17 |
| 2 | Licensed Microbanks | API | `licensedMicrobanks` | 2 |
| 3 | Microfinance organizations | Excel (EN) | `MFI` sheet | 28 |
| 4 | Credit Unions | Excel (EN) | `Credit Unions` sheet | 1 |
| 5 | Loan Issuing Entities | Excel (KA) | `სგს რეესტრი` sheet | 137 |
| 6 | Currency Exchange Units | Excel (KA) | `რეგისტრირებული` sheet | 500 |
| 7 | Brokerage Companies | API | `licensedParticipantsBrokerageCompanies` | 11 |
| 8 | Securities Registrars | API | `licensedParticipantsSecuritiesRegistrars` | 3 |
| 9 | Stock Exchanges | API | `licensedParticipantsLicensedStockExchange` | 2 |
| 10 | Central Depository | API | `licensedParticipantsLicensedCentralDepository` | 1 |
| 11 | Investment Funds | API | `investmentFundsInvestmentFunds` | 24 |
| 12 | Asset Management Companies | API | `investmentFundsInvestmentFundManagementCompany` | 11 |
| 13 | Specialized Depositaries | Content table | `investmentFundsSpecializedDepositories` (content/details) | 3 |

**Total: 740 entities.**

> Note on L13: its `/organizations` endpoint is empty; the 3 entities (JSC Halyk Bank Georgia, JSC TBC Bank, JSC Bank of Georgia) are published as an HTML table in the tab's `content/details` `description`. Columns: Name · ID · Order Number · Order Date · Granted Status · Contact → mapped to Name · InternalID_1 (Identification Code) · InternalID_2 (Order Number) · RegulationDate · Phone.

## Key decisions

- **Head offices only (L5, L6).** The loan-issuing and currency-exchange registers list both head offices (`სათაო`) and branches (`ფილიალი`); branches share the same name + ID code as their head office. Only `სათაო` rows are kept (L5: 137 of 274, L6: 500 of 701). The cancelled/`გაუქმებული` sheets are ignored.
- **Translation (L5, L6 are Georgian).** Per the "translate if possible" instruction: `Name` **keeps the original Georgian** (preserve-original convention), and the English translation is written to `Name - Mother Company`. `City`, region (→`Address_2`) and legal form (→`CoType`) are translated to English. Street `Address_1` is kept in Georgian.
  - Translation uses Google's `gtx` endpoint (`translate.googleapis.com/translate_a/single`) called with `verify=False`. This was necessary because (a) the installed `googletrans` 3.4.0 is async and (b) `deep_translator` fails TLS verification behind the corporate self-signed certificate. The same `verify=False` is used for all NBG requests for the same reason. Results are cached per unique string.

## Field mapping

- **API / banks:** `title`→Name; `identificationCode`→InternalID_1 (Identification Code) or `licenseNumberBank`→InternalID_1 (License No.); `licenseOrOrderNumber`→InternalID_2; `contactInfo` split into Phone / Email / Website; `link`→Website; `releaseDate`→RegulationDate.
- **Excel:** registration/licence №→InternalID_1; identification code→InternalID_2; legal form→CoType; region→Address_2; city→City; address→Address_1; web-page→Website (L3); legal-act date→RegulationDate.

## Output

`GE_NBG_v1.ipynb` → `GE NBG SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`). Excel registers are downloaded into `tempfolder/` (cleared at the start of each run).
