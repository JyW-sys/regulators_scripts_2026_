# HR HANFA — Hrvatska agencija za nadzor financijskih usluga

Croatian Financial Services Supervisory Agency (HANFA).
Jira: **DECD-6823**

- Scraper: `HR_HANFA_v1.py` (`python3 HR_HANFA_v1.py`)
- Notebook: `HR_HANFA_v1.ipynb` (generated from the `.py`, executed end to end, 6 cells, 0 errors)
- Output: `HR HANFA SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, sheet `SQL Ready`, written to this folder
- Source type: HTML tables (`requests` + BeautifulSoup) **plus** a JSON DataTables endpoint for 5 large registers. No browser, no Selenium/DrissionPage, no OCR.

## Lists

Each of the 6 ticket lists is a *section* of `https://www.hanfa.hr/registers/` that fans out into
several sub-registers. 31 sub-registers are in scope. `Typology` carries the sub-register title
so a row can always be traced back to the exact page it came from.

| ListNr | ListCode | ListLabel | ListName | Section URL | Sub-registers in scope | Rows |
|---|---|---|---|---|---|---|
| 1 | 1 | 4 | List of Investment firms | https://www.hanfa.hr/registers/investment-firms/ | 3 | 34 |
| 2 | 2 | 4 | List of Investment funds | https://www.hanfa.hr/registers/investment-funds/ | 7 | 193 |
| 3 | 3 | 4 | List of Pension System | https://www.hanfa.hr/registers/pension-system/ | 5 | 51 |
| 4 | 4 | 2 | List of Insurance Market | https://www.hanfa.hr/registers/insurance-market/ | 14 | 11,569 |
| 5 | 5 | 4 | List of Leasing Companies | https://www.hanfa.hr/registers/leasing/ | 1 | 15 |
| 6 | 6 | 4 | List of Factoring Companies | https://www.hanfa.hr/registers/factoring/ | 1 | 3 |
| | | | | | **31** | **11,865** |

**ListLabel justification** (1 = bank, 2 = insurance, 3 = both, 4 = everything else).
HANFA is Croatia's **non-banking** financial supervisor — banking licences are issued by the
Croatian National Bank (HNB), not by HANFA. Only list 4 is an insurance register, so it gets `2`;
investment firms, funds, pensions, leasing and factoring all get `4`.
See "judgment calls" below for the one debatable case (list 1 contains banks).

**RegulationType** = `Regulated` on every row. All 31 in-scope sub-registers are positive
authorisation/registration registers. The negative ones (`... in liquidation`) and the
passporting notices (`Notifications from EU Member States`) are excluded by the ticket, so no
row in this output needs a cancellation/revocation treatment.

## Row-count reconciliation

The 5 large registers are `serverSide: true` DataTables and publish their own total
(`recordsTotal` in the API response, and `deferLoading: N` in the page source). Scraped vs
site-declared, from the run of **2026-08-20 18:41**:

| Sub-register | Scraped | Site declares | Match |
|---|---|---|---|
| UCITS | 109 | 109 | yes |
| Insurance agencies | 349 | 349 | yes |
| Insurance representation crafts | 549 | 549 | yes |
| Insurance agents / brokers / ancillary intermediaries | 10,333 | 10,333 | yes |
| Certified actuaries | 187 | 187 | yes |

The remaining 26 sub-registers render their whole `<tbody>` server-side and publish no counter
(`n-a` in the run log); the scraped count equals the number of `<tr>` in the table, which is
exactly what the page shows once "Show 100 rows" is selected.

Per sub-register, as scraped:

| List | Sub-register | Source | Rows |
|---|---|---|---|
| 1 | Investment firms | HTML | 21 |
| 1 | Tied agents | HTML | 11 |
| 1 | Local intermediary | HTML | 2 |
| 2 | UCITS management companies | HTML | 8 |
| 2 | AIF management companies - licensed | HTML | 17 |
| 2 | AIF management companies - registered | HTML | 5 |
| 2 | UCITS | API | 109 |
| 2 | AIFs - licensed | HTML | 49 |
| 2 | AIFs - registered | HTML | 4 |
| 2 | Special funds | HTML | 1 |
| 3 | Mandatory pension companies | HTML | 4 |
| 3 | Voluntary pension companies | HTML | 4 |
| 3 | Mandatory pension funds | HTML | 12 |
| 3 | Voluntary pension funds | HTML | 29 |
| 3 | Pension insurance companies | HTML | 2 |
| 4 | Insurance companies and reinsurance companies | HTML | 14 |
| 4 | Credit institutions | HTML | 17 |
| 4 | Insurance agencies | API | 349 |
| 4 | Insurance and/or reinsurance brokerage companies | HTML | 77 |
| 4 | Insurance representation crafts | API | 549 |
| 4 | Insurance agencies conducting insurance business at vehicle roadworthiness test garages | HTML | 25 |
| 4 | Insurance representation crafts conducting insurance business at vehicle roadworthiness test garages | HTML | 6 |
| 4 | Croatian Post and Financial Agency | HTML | 1 |
| 4 | Insurance agents, insurance and/or reinsurance brokers, ancillary insurance intermediaries | API | 10,333 |
| 4 | Certified actuaries | API | 187 |
| 4 | Branch - insurance companies and/or reinsurance companies from EU Member States | HTML | 4 |
| 4 | Insurance and/or reinsurance representation crafts | HTML | 6 |
| 4 | Ancillary Intermediary turist agencies | HTML | 1 |
| 4 | Other Ancillary Intermediaries | HTML | 0 (the register is genuinely empty on the site) |
| 5 | Leasing companies | HTML | 15 |
| 6 | Factoring companies | HTML | 3 |

No deduplication is performed anywhere. If an entity appears in two sub-registers it produces two
rows, distinguishable by `Typology`.

## Excluded by the ticket

Resolved by matching the anchor's **visible label** (accent-stripped, lower-cased, substring),
never by URL slug:

- `notifications` → `Notifications from EU Member States` (investment firms, investment funds),
  `Notifications - insurance companies and/or reinsurance companies from EU Member States`,
  `Notifications - insurance agents and brokers from EU Member States`.
- `in liquidation` → `UCITS in liquidation`, `AIFs in liquidation`,
  `Leasing companies in liquidation`, `Factoring companies in liquidation`.

This exclusion also does the narrowing the ticket wants for lists 5 and 6: the leasing and
factoring sections each hold exactly two sub-registers, one of which is the "in liquidation" twin,
so the section resolves down to the single URL quoted in the ticket.

`Virtual currencies` and `Crypto-asset market` sit on the same registers page but are **not**
in any of the 6 ticket lists and are not scraped.

## Site quirks (things that will break this scraper later)

1. **Two delivery mechanisms behind one widget.** Most registers server-render the full `<tbody>`;
   5 of them are `serverSide: true` DataTables that render only the first 10 rows and load the
   rest from `POST /Api/Registers/GetData`. **If the server-side detection ever fails, those
   registers silently drop from ~11,500 rows to 50** — the scraper would still "work". The
   detection reads `serverSide: true` plus the per-register GUID (`d.Key = '...'`) out of the
   inline script at run time; the GUIDs are never hard-coded. If HANFA renames that JS variable,
   the counts collapse. The scraped-vs-declared table printed at the end of every run is the
   tripwire — check it.
2. **The API returns dates in a different format from the HTML.** The pages show `04/12/2015`;
   the JSON returns the same date as `04. 12. 2015` (dots plus spaces). The first version of this
   scraper lost every date on the 5 server-side registers because of it. `parse_date` now
   tolerates whitespace around the separator.
3. **Croatian labels leak into the English pages.** `/registers/investment-firms/tied-agents/` is
   served under the English tree but its detail cells are labelled `Sjedište:`, `Telefon:`,
   `OIB:`, `RBS:`, `Internetska stranica:`. Label matching is accent-stripped and lower-cased,
   and `LABEL_MAP` carries both languages. Content values are frequently Croatian even on EN
   pages (e.g. insurance classes, leasing activity `Operativni, Financijski`) — not translated.
4. **The real data lives in hidden cells.** The columns behind the DataTables `+` control
   (`<td class="detalji" style="display:none">`) are present in the HTML/JSON payload, so no
   clicking is needed — but they are `<span>Label:</span> value<br/>` blobs, not columns. All
   address / phone / website / LEI / BIC / OIB values come from parsing those blobs.
5. **Column layout differs per sub-register.** 31 pages, no two header sets identical (8 distinct
   shapes). Everything is mapped by normalised header label, never by index.
6. **`Other Ancillary Intermediaries` currently returns 0 rows.** That is the site's real state
   (empty table), not a scraper failure. If it stays 0 forever it is worth re-checking.
7. **Corporate TLS proxy**: all requests use `verify=False` with urllib3 warnings disabled.

## Field mapping

Common to every row: `RegCtry=HR`, `RegCode=HANFA`, `ListLanguage=EN`, `RegulationType=Regulated`,
`Cntry=HR` (see the branch exception), `ListProcessDate = now.strftime('%Y-%m-%d')`,
`ListCode`/`ListName`/`ListLabel` from the tables above. Every record goes through a single
`add_row()` that fills all 43 keys and raises `KeyError` on an unknown column, so the schema
cannot drift.

| sqldict column | Source |
|---|---|
| `Name` | header `Name` / `Fund` / `Tied agent`; for the natural-person register (`Insurance agents…`) `Name` + `Surname` are joined, and `Certified actuaries` likewise |
| `Typology` | sub-register title (the page the row came from) |
| `CoType` | header `Category` (AIF management companies) or `Intermediary status` |
| `License_Type` | `Approved activities`, `Classes`, `Activity`, `Line of business`, `Type of Insurance`, `Category of Intermediary…`, `Tied agents activities`, `Manner of provision of services` — joined with ` \| `, deduplicated |
| `InternalID_1/2/3` (+ `_type`) | in priority order: `OIB` (Croatian tax ID, also labelled `Personal identification number:`), `Registration Number` (also `Craft registration number:`, `RBS:`), `ISIN` (funds), `HANFA Register ID` (the hidden `R195`-style code). Capped at 3 — this is the only place where data can be dropped |
| `Address_1`, `City`, `Zip` | `Address:` / `Sjedište:` detail label, split on the last comma; a leading 4–5 digit postcode in the city part becomes `Zip` |
| `Phone` | `Phone:` / `Telefon:` |
| `Website` | `Website:` / `Internetska stranica:` |
| `Email` | `E-mail:` where present |
| `LEI Code` | `LEI` header column (funds) or `LEI:` detail label |
| `BIC SWIFT Code` | `BIC:` detail label (investment firms only) |
| `Name - Mother Company` | `Management company` (funds, pension funds) or `Investment firm` (tied agents) |
| `RegulationDate` | `Date of registration` / `Date of Authorisation`, normalised to `YYYY-MM-DD` |
| `Cntry` | `HR`, except `Branch - insurance companies… from EU Member States` where the `EU Member State` column is mapped to its ISO-2 code (the entity's home country) |

Fill rates on the 2026-08-20 run (11,865 rows): `Name` 100%, `InternalID_1` 98.4%,
`Address_1` 92.2%, `City` 92.1%, `License_Type` 88.0%, `RegulationDate` 10.0% (1,187 rows —
only some registers publish a date), `LEI Code` 3.0%, `Website` 0.7%, `Phone` 0.6%,
`BIC SWIFT Code` 0.1%. The low contact-detail rates are the site's, not the parser's: the
10,333-row natural-person register carries only address + IDs.

## Judgment calls for the requester

1. **List 1 `ListLabel = 4`, but the register contains banks.** `Investment firms` lists
   Addiko Bank d.d., AGRAM BANKA d.d., CROATIA BANKA d.d.,
   Erste&Steiermärkische Banka dioničko društvo etc. — credit institutions
   holding a MiFID investment-services authorisation. It was labelled `4` because it is an
   investment-services register, not a banking-licence register (HNB issues those). If the
   requester wants bank coverage from it, `1` or `3` would be defensible.
2. **List 4 sub-register `Credit institutions` is inside the insurance list.** These are banks
   registered as *insurance intermediaries*. It inherits `ListLabel = 2` from its list. Flagging
   in case the requester wants it split out.
3. **Natural persons dominate the output.** `Insurance agents, insurance and/or reinsurance
   brokers, ancillary insurance intermediaries` is 10,333 of the 11,865 rows and they are
   individuals, not companies (`Name` = given name + surname). Same for `Certified actuaries`
   (187). Confirm these should be loaded as entities; if not, the total drops to 1,345.
4. **Columns with no home in the 43-key schema, currently dropped**: `Responsible person`,
   `Name of represented companies`, `Member States where crossborder activities are notified`,
   `Competent authority`, `Link to the Court register` (a `sudreg.pravosudje.hr` URL carrying the
   court MBS number), and the per-intermediary `Extract` PDF link. Say the word and any of them
   can be folded into an `InternalID_*` or `License_Type`.
5. **More than 3 identifiers on some rows.** Insurance agencies carry OIB + registration number +
   HANFA register id; only the first 3 are kept, which is currently never lossy, but a future
   fourth ID would be dropped silently.
6. **Values stay in Croatian.** Insurance classes, leasing activities and some company-form
   suffixes are Croatian even on the EN pages. No translation was applied — confirm whether the
   requester wants `License_Type` translated.
7. **`Virtual currencies` and `Crypto-asset market`** registers exist on the same page and are not
   covered by the ticket. Confirm they are genuinely out of scope.
