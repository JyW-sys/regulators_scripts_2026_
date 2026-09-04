# AO BNAO

## Regulator Information

- **Country/Region Code**: AO
- **Regulator Code**: BNAO
- **Full Name**: Banco Nacional de Angola (National Bank of Angola)
- **Website**: https://www.bna.ao/#/pt/supervisao/politica-macroprudencial/inst-financeiras-autorizadas
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6964 (story DECD-3438, "Regulators 2026 - Internal Crawlers")

> **Naming note.** The work request that produced this folder said "AO BNRO". No Jira
> ticket and no folder by that name exists anywhere — `parent = DECD-3438 AND summary ~ "BNRO"`
> returns nothing. The only Angola subtask under DECD-3438 is **DECD-6964 "AO BNAO"**
> (Banco Nacional de Angola), so the folder, the codes and the files follow the ticket
> summary: `RegCode = 'BNAO'`.

## Script

- **Current Version**: `AO_BNAO_v1.py` (identical logic also provided as `AO_BNAO_v1.ipynb`, 8 cells,
  generated from the `.py` and asserted byte-identical to it)
- **Output**: `AO BNAO SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, sheet `SQL Ready`, **141 rows**,
  43 columns — the house naming convention
  (`filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])`).
  The `_vN` suffix belongs on the script, never on the workbook.
- **Approach**: plain `requests` (desktop UA, `verify=False`) against BNA's JSON API, then
  `pdfplumber` on the PDF it points to. No browser is needed.

## List Types

The Jira description defines exactly **one** list:

| ListNr | ListName (emitted) | ListName in Jira | ListLabel | Rows |
|---|---|---|---|---|
| 1 | Instituições Financeiras Autorizadas | ~~Instituicoes financieras autorizadas~~ | 1 | 141 |

**`ListName` follows the source page, not the Jira description** (ticket owner's decision,
2026-09-02). Jira writes *financieras*, which is Spanish; BNA is a Portuguese-language
regulator and names the section **Instituições Financeiras Autorizadas** — verified against the
live API's own `Categoria` value, `Política Macroprudencial - Instituições Financeiras
Autorizadas`, and the page slug `inst-financeiras-autorizadas`. The accented form is safe on
the cp1252 control server: `ListName` is never printed, it only travels into the UTF-8 workbook.

The PDF's nine internal sections are **not** separate Jira lists. They are carried on every
row as `License_Type` (the section heading, verbatim Portuguese) and `CoType` (an English
descriptor):

| PDF section (verbatim) | CoType | Rows |
|---|---|---|
| INSTITUIÇÕES FINANCEIRAS BANCÁRIAS | Bank | 23 |
| CASAS DE CÂMBIO | Foreign Exchange Bureau | 24 |
| CASAS DE CÂMBIO AUTORIZADAS A EXERCER ACTIVIDADE DE REMESSA DE VALORES | Foreign Exchange Bureau - Money Remittance | 22 |
| SOCIEDADES DE MICROCRÉDITO | Microcredit Company | 22 |
| SOCIEDADES PRESTADORAS DE SERVIÇOS DE PAGAMENTOS | Payment Service Provider | 18 |
| FUNDOS | Fund | 2 |
| COOPERATIVAS DE CRÉDITO | Credit Cooperative | 3 |
| ESCRITÓRIOS DE REPRESENTAÇÃO DE BANCOS ESTRANGEIROS | Representative Office of a Foreign Bank | 2 |
| OPERADORES DE MICROCRÉDITO | Microcredit Operator | 25 |
| | **Total** | **141** |

### ListLabel — judgment call

`ListLabel = 1` (bank) for the whole list. Rule: 1 = bank, 2 = insurance, 3 = both,
4 = everything else. This is BNA's single register of authorised credit and financial
institutions and it is headed by the country's 23 licensed banks plus credit cooperatives.
Angolan insurers are supervised by **ARSEG**, not BNA, so nothing in this document is an
insurance entry — 2 and 3 are impossible. The alternative reading (call it 4 because the
list also carries exchange bureaux, microcredit operators and payment institutions) was
rejected because that would leave Angola's banks with no bank-labelled list at all. This
mirrors `MZ BMO`, where deposit-taking credit institutions are labelled 1.

## How the source is reached

`bna.ao` is an Angular SPA with hash routing. The HTML served at the Jira URL is a 7 KB
shell identical for every route, so there is nothing to scrape from the page itself. The
list component (lazy chunk `587.*.js`) drives a SharePoint back end behind a Java proxy:

```
POST https://www.bna.ao/service/rest/generic/sharepoint/v2/search
{"url": "Supervisão",
 "parameters": {"$top": 1000,
                "$orderby": "DataDePublicacao desc",
                "$filter": "Categoria eq 'Política Macroprudencial - Instituições Financeiras Autorizadas' and Visualizar eq 1"}}
```

The category currently holds **two** documents:

| ID | DataDePublicacao | Idioma | Title |
|---|---|---|---|
| 272 | 2025-12-09 | Português | Lista das Instituições Financeiras Autorizadas - Dezembro 2025 |
| 178 | 2023-02-22 | Inglês | List of Authorised Financial Institutions - January 2023 |

The Jira comment says "click in the most recent list", so the script sorts by
`DataDePublicacao` descending and takes the newest — **ID 272**. No `Idioma` filter is
applied, deliberately: the SPA hard-codes `Idioma eq 'Português'`, but filtering that way
here would silently return nothing if BNA ever republishes in English only.

### Trap: the stale index endpoint

`GET https://www.bna.ao/service/rest/generic/sharepoint/supervisao` answers **200 with ~63
records** and looks like the right index. It is stale — it contains ID 178 (January 2023)
and does **not** contain ID 272. A scraper built on it returns a three-year-old list with no
error. Do not use it.

### Download

Each record's `OData__dlc_DocIdUrl.Url` points at an **internal** host
(`http://172.20.42.86/sites/cms/_layouts/15/DocIdRedir.aspx?ID=...`) that is not reachable
from outside. The public proxy takes the path tail after `cms/`:

```
https://www.bna.ao/service/rest/file/getPDF/v2?url=_layouts/15/DocIdRedir.aspx?ID=AE2CRDQUTFAC-1955507033-272
```

The second `?` is left **unencoded** — that is what the app itself sends, and it works
(200, 205,265 bytes, `%PDF-`). The internal URL is used only as a key, never fetched.

The proxy intermittently answers **502**; both the search call and the download retry 5×
with a 4 s pause. This was observed live during development, not assumed.

## PDF structure & parsing

4 pages, real ruled tables, selectable text — **no OCR needed**. Nine sections, each
numbering its own rows from 1. Three column shapes:

```
NOME | SIGLA            | N.º DE REGISTO    (banks only)
NOME | PAÍS DE ORIGEM                       (foreign-bank rep. offices, 3 columns)
NOME | PROVÍNCIA / SEDE | N.º DE REGISTO    (all other sections)
```

Four hazards, all handled:

1. **Page-break orphan *outside* the table.** A section continuing onto a new page has its
   first row drawn above the detected table bbox (the top border is not redrawn), so
   `find_tables()` drops it entirely. Those rows are recovered from the gap band above each
   table by grouping words into lines (`round(top/3)`) and bucketing them against *that
   table's own* column x-edges, so they split into columns exactly like the ruled rows.
   Lines whose only non-empty cell is the leading number are rejected — that filter is what
   keeps page numbers and footnote markers out.
2. **Page-break orphan *inside* the table with undrawn cell borders.** On page 2 the
   continuation row keeps its number cell but the name/seat/registration cells have no top
   border, so `extract()` returns `['16', None, None, None]` — a hollow row that looks valid
   to a contiguity check but has no data. Any row whose leading cell is a number and whose
   remaining cells are all empty is re-bucketed from the words in that row's own y-band.
   Exactly **1** row in the current edition (`CASAS DE CÂMBIO` #16, RUCÂMBIO / LUANDA / 678).
   The run prints `hollow rows repaired: 1`.
3. **Phantom columns.** Some tables are detected 6 or 8 columns wide because of stray
   vertical rules. Columns empty in *every* data row of that table are collapsed away,
   normalising each section back to its real 3 or 4 columns.
4. **A super-heading with no table.** `SOCIEDADES NÃO FINANCEIRAS PRESTADORES DE SERVIÇOS DE
   MICROCRÉDITO` groups the two microcredit sections that follow it. It must not open a
   section of its own, or every subsequent row lands under the wrong heading.

### pdfplumber portability — do not reintroduce `Table.columns`

The column x-edges that hazards 1 and 2 bucket against were originally read from
`t.columns`. That attribute exists only in recent pdfplumber, and the control server's build
does not have it, so the production run died with:

```
File "AO-BNAO.py", line 369, in parse_pdf
    edges = [c.bbox[0] for c in t.columns] + [t.columns[-1].bbox[2]]
AttributeError: 'Table' object has no attribute 'columns'
```

A pdfplumber column is nothing but the table's cells grouped by their left edge
(`Table._get_rows_or_cols` groups `self.cells` on `x0`), so `col_edges(t)` now derives the
same list from `t.cells`, which every version has:

```python
xs = sorted(set(c[0] for c in t.cells))
last = max(c[2] for c in t.cells if c[0] == xs[-1])
return xs + [last]
```

Verified byte-identical to the old expression on all **11** detected tables of the current
edition, and the workbook is unchanged apart from `ListProcessDate`. `t.rows`, `t.bbox`,
`t.extract()`, `page.find_tables()`, `page.crop()` are all long-standing API and were left
alone. **If this file is edited again, keep using `t.cells` — `t.columns` will pass on a dev
machine and crash on the control server.**

### Self-validation

Each section numbers its rows 1..N, so after parsing the script asserts that every section's
sequence is exactly `range(1, N+1)` **and** that no row has an empty `Name`. A dropped,
doubled or hollow row fails the run loudly rather than shrinking the output silently. Both
hazards 1 and 2 above were found by this assert, not by eyeballing.

### Duplicate registration numbers are correct — do not dedupe

Sections 2 and 3 legitimately overlap: all 22 exchange bureaux additionally authorised for
cash remittances are listed in **both** `CASAS DE CÂMBIO` and `CASAS DE CÂMBIO AUTORIZADAS A
EXERCER ACTIVIDADE DE REMESSA DE VALORES`, with the **same** `N.º de Registo`. So
`InternalID_1` has 22 duplicate values by design. In 13 of the 22 pairs the two sections even
spell the name differently — a short form in one and the full legal form in the other
(`NOVACÂMBIOS` / `NOVACÂMBIOS, S.A.`; `UNIVERSAL` / `UNIVERSAL CÂMBIOS, LDA`; `AGDN` /
`AGDN – CASA DE CÂMBIOS, LDA`). Both rows are emitted because the source shows both rows.

## Field mapping

| Output column | Source |
|---|---|
| `Name` | `NOME`, verbatim Portuguese, with status markers and `(SM)` stripped |
| `InternalID_1` / `_type` | `N.º DE REGISTO` / `N.o de Registo` |
| `InternalID_2` / `_type` | `SIGLA` / `Sigla` — banks only |
| `City` | `PROVÍNCIA / SEDE` verbatim (e.g. `LUANDA`, `HUÍLA`, `ZAIRE / SOYO`) |
| `Cntry` | `AO` |
| `Cntry - Mother company` | `PAÍS DE ORIGEM` mapped to ISO — rep. offices only (`ALEMANHA`→`DE`, `ÁFRICA DO SUL`→`ZA`) |
| `CoType` | English descriptor per section (table above) |
| `License_Type` | PDF section heading, verbatim Portuguese |
| `RegulationType` | `Regulated`, or a status from the footnote legend (below) |
| `RegCtry` / `RegCode` / `ListCode` | `AO` / `BNAO` / `1` |
| `ListLanguage` | from the winning record's `Idioma` → `PT` |
| `ListValidityDate` | the document's `DataDePublicacao` → `2025-12-09` |
| `ListName` | `Instituições Financeiras Autorizadas` — the source page's own name, NOT Jira's `Instituicoes financieras autorizadas` (see the list table above) |
| `ListProcessDate` | run date, `%Y-%m-%d` |

### Language

Names are kept **verbatim in Portuguese** and are never machine-translated. This follows
`MZ BMO` v1→v2, where translating Portuguese names destroyed proper nouns and the output was
rejected. Only `CoType` and the ISO country codes are English.

### Fields the source does not publish

This document is name + abbreviation/seat + registration number and nothing else. There is
**no address, phone, fax, e-mail, website or authorisation date anywhere in it**, so
`Address_1`, `Address_2`, `Zip`, `Phone`, `Fax`, `Website`, `Email`, `RegulationDate`,
`CancellationDate`, `LEI Code` and `BIC SWIFT Code` are left empty rather than invented.
`City` is empty for the 23 banks and the 2 representative offices because those two sections
have no seat column at all (82.3% overall fill).

### Status markers — judgment call

Footnote legends read verbatim out of the PDF:

| Page | Legend (verbatim) | Applied as |
|---|---|---|
| 1 | `* Banco em liquidação, após dissolução voluntária.` | `RegulationType = Inactive License` |
| 1 | `** Banco em processo de início de actividade` | `RegulationType = Not Operational` |
| 3 | `* Sociedade de Microcrédito Avança na Vida - Com actividade suspensa` | `RegulationType = Inactive License` |
| 3 | `* (SM) – Serviços móveis` | **not** a status — see below |

Three rows are affected:

| Name | Section | RegulationType |
|---|---|---|
| AFRICAN BANK OF OMAN, S.A. | INSTITUIÇÕES FINANCEIRAS BANCÁRIAS | Not Operational |
| BANCO VTB ÁFRICA, S.A. | INSTITUIÇÕES FINANCEIRAS BANCÁRIAS | Inactive License |
| AVANÇA NA VIDA, LDA. | SOCIEDADES DE MICROCRÉDITO | Inactive License |

The remaining 138 rows are `Regulated`. `Inactive License` and `Not Operational` are both
existing values in this repo's `RegulationType` vocabulary — no new value was invented. The
marker→status mapping is keyed on **(section, marker)** because `*` means different things in
the bank section and the microcredit section. An **unmapped** marker aborts the run with the
offending rows listed, so a future edition that adds a new footnote forces a human to read
the new legend instead of silently defaulting to `Regulated`.

`(SM)` is a **licence-scope** note (mobile services) on 12 payment institutions, not a status.
It is stripped from `Name` and recorded by appending ` - Serviços Móveis` to `License_Type`;
`RegulationType` stays `Regulated` and `CoType` stays `Payment Service Provider`.

## Output safety

- Column list is asserted equal to the fixed 43-key project schema, in order.
- `InternalID_*`, `Zip`, `Phone`, `Fax` and the mother-company `Zip`/`Phone` are forced to
  `str` before writing, because Excel otherwise turns all-digit IDs into floats and eats
  leading zeros.
- The workbook is **read back** after writing and re-checked: row count unchanged, column set
  unchanged, no text column contains `.` or `e+`, and the `InternalID_1` non-empty count
  matches the DataFrame. This catches silent coercion that a row-count check would miss.
- The PDF is downloaded into `tempfolder/`. At the end the folder's **contents** are removed
  and the **directory is kept** — that is the project convention (`regulator-temp-downloads`
  skill; 56 sibling scripts use the bounded `os.remove` loop, only 2 use `rmtree`, and 181
  regulator folders ship a `tempfolder/`). The delete is guarded by an assert that the path is
  absolute, named `tempfolder`, and sits directly inside this regulator folder.
- The `.xlsx` is written to the **regulator folder**, not to `tempfolder/`.
- Nothing scraped is `print()`ed — only counts and ASCII-safe summaries — because the Windows
  control server console is cp1252 and raises `UnicodeEncodeError` on Portuguese text.

## QA (2026-09-02)

No `qa_positive_combined` baseline exists for AO, so fallback checks were used.

- Rows **141**, columns **43**, `ListCode 1: 141`.
- Non-empty rates: `Name` 100%, `Cntry` 100%, `CoType` 100%, `License_Type` 100%,
  `RegulationType` 100%, `ListProcessDate` 100%, `ListValidityDate` 100%,
  `InternalID_1` 98.6% (the 2 rep. offices have no registration number),
  `City` 82.3% (banks and rep. offices have no seat column),
  `Address_1` / `Phone` / `Website` 0% — **not published by the source**.
- Encoding: `Ã©` 0, `â€™` 0, `Â ` 0, `?{3,}` 0, U+FFFD 0. 13 rows contain a literal `Ã`
  somewhere (11 of them in `Name`, 2 only via the `REPRESENTAÇÃO` heading in `License_Type`);
  all were inspected and are legitimate Portuguese (`PRESTAÇÃO`, `GESTÃO`, `COMÉRCIO`,
  `REPRESENTAÇÃO`), not mojibake.
- `Name` content: 0 empty, 0 all-digit, 0 `Yes`/`No`, 0 residual `*` or `(SM)`;
  132 distinct names over 141 rows (the 9 repeats are the exchange-bureau overlap where both
  sections use the identical spelling).
- `InternalID_1`: 0 non-numeric, 0 float-formatted. 22 duplicates — expected, see above.
- The notebook was executed end-to-end with `nbclient`; its output workbook was read back and
  is **exactly equal** (`DataFrame.equals`) to the one the `.py` produces.
- A stray early build wrote `AO_BNAO_v1.xlsx`, which breaks the naming convention. It is kept
  only for comparison and is byte-for-byte the same data as the correctly named workbook; it
  can be deleted.

## Known unknowns

- BNA appears to publish only the current edition per language; the category returns 2
  documents, not a dated archive. Whether older editions exist behind another category was
  **not** verified.
- The live DOM was never rendered — DrissionPage's CDP handshake fails behind this machine's
  corporate proxy. Every conclusion above comes from the JS bundles plus replayed API calls,
  which plain `requests` reproduces, so this did not block the scrape.
