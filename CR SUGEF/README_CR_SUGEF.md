# CR SUGEF

## Regulator Information

- **Country/Region Code**: CR
- **Regulator Code**: SUGEF
- **Full Name**: Superintendencia General de Entidades Financieras (Costa Rica)
- **Website**: https://www.sugef.fi.cr/
- **Jira**: DECD-6822
- **Language**: Spanish (`ListLanguage = ES`)

## Script

- **Current Version**: `CR_SUGEF_v1.py` (notebook twin: `CR_SUGEF_v1.ipynb`)
- **Approach**: the `.aspx` index page is plain HTML — no postback / viewstate needed, so a
  single `requests.get` (`verify=False`, desktop User-Agent, urllib3 warnings disabled) is
  enough. The selected PDF is downloaded into `tempfolder/` and parsed with **`pdfplumber`**
  (text layer present — **no OCR needed**).

## List Types

| ListNr | ListName | URL | ListLabel | Comments |
|--------|----------|-----|-----------|----------|
| 1 | Entidades Supervisadas | https://www.sugef.fi.cr/entidades_supervisadas/lista_entidades_supervisadas_por_SUGEF.aspx | 1 | Index page of ~344 published PDF editions. The code selects the **most recent** edition and collects **item 1 only** (page 1 + the top of page 2). |

### ListLabel justification

`ListLabel = 1` (bank list). Item 1 of the PDF is made up exclusively of deposit-taking /
credit institutions: state commercial banks, banks created by special laws, private banks,
non-bank finance companies, savings & credit co-operatives, mutual savings & loan
associations, and one "other financial entity" (Caja de Ahorro y Préstamos de la ANDE).
No insurer appears anywhere in item 1 — Costa Rican insurers are supervised by SUGESE, not
SUGEF — so `2` (insurance) and `3` (bank & insurance) are both wrong, and `4` (everything
else) would understate a list whose core is the country's banks.

## Selecting the most recent PDF (nothing is hard-coded)

The Jira comment cites `.../ver/entidades_supervisadas/.../entidades_fiscalizadas/2024/2024_09.pdf`.
**That URL is already dead** — it now returns an HTML error page with HTTP 200 (a soft 404),
not a PDF. This is exactly why the edition must be resolved from the index page every run.

1. Fetch the index page and collect every `<a>` whose `href` ends in `.pdf` and contains the
   path segment `entidades_fiscalizadas`.
2. Each edition is linked from **several** anchors ("Lista de entidades", the year, "Pdf",
   and the publication date). The date anchor carries `dd/mm/yyyy` text, so the script keeps
   the date found on *any* anchor pointing at a given URL.
3. Sort by that parsed date, descending, and take the first.
4. `download_pdf()` asserts the response really starts with `%PDF`, so a soft-404 HTML page
   can never be parsed as if it were a list.

**The file name must never be used to rank editions.** `<YEAR>_<NN>.pdf` is a *sequence*
number, not a month: `2024_09.pdf` is the **05/11/2024** (November) edition — the very one
the ticket refers to. Editions are also spread over three directories (`actual/`,
`anterior/`, and the bare `entidades_fiscalizadas/` root), so directory is not a ranking
signal either. Only the anchor date is.

The run log prints the five most recent editions and the one that was selected.

## What "item 1" is, and where it stops

Item 1 is the heading

```
1. ENTIDADES SUPERVISADAS POR LA SUGEF ACTUALIZADA AL 03 DE JULIO DE 2026
```

with subsections `1.1 … 1.7`. It runs from the top of page 1 to roughly the middle of
page 2. Item 2 (`CONGLOMERADOS Y GRUPOS FINANCIEROS`), item 3 (`MERCADO DE DERIVADOS
CAMBIARIOS`) and everything after are **not** collected.

### Boundary detection (structural, not positional)

No page number, line count or heading wording is hard-coded. `pdfplumber` word attributes
give three independent signals:

| Element | Font | Left indent |
|---|---|---|
| Top-level heading (`1.`, `2.`, `3.`) | **bold** | x0 ≈ 56.7 |
| Subsection heading (`1.1`, `1.2`, …) | **bold** | x0 ≈ 92.2 |
| Entity row (`1.`, `2.`, …) | regular / italic | x0 ≈ 127.5 |
| Footnote marker (`NG-1/`, `DC-3`) | any | size 6.5 |

- **Start** = the bold top-level heading numbered `1`; its x0 is remembered as the section indent.
- **Stop** = the next bold top-level heading at that same indent whose number is not `1`.

Entity rows are numbered too (`2. Banco BCT S.A.`), but they are neither bold nor at the
section indent, so they can never be mistaken for the item-2 heading. Words below
`MIN_FONT_SIZE = 8` are dropped first, which removes the superscript footnote markers.

### Row assembly

- A line opens a **new** entity only if it starts with the *next expected sequence number*
  within the current subsection; anything else in the same column is a wrapped continuation
  of the previous name. This correctly rebuilds
  `Grupo Mutual Alajuela – La Vivienda de Ahorro y Préstamo` and
  `Davibank (Costa Rica) S.A. (antes Scotiabank de Costa Rica S.A.)` from two physical lines.
- A continuation must start within `COL_TOLERANCE = 25pt` of the entity column, which is what
  keeps the page footer (`Página 1 de 12` at x0 ≈ 515, `Uso Interno` at x0 ≈ 282) from being
  glued onto the last co-operative. Footers are additionally dropped by regex.
- Any line that matches neither rule is printed as `[skip] unmatched line …` — never dropped
  silently.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | entity name as printed in item 1 |
| InternalID_1 / InternalID_1_type | *cédula jurídica* (`\d-\d{3}-\d{6}`) / `Cedula Juridica` |
| CoType | English translation of the subsection (`Private Bank`, `Savings and Credit Cooperative`, …); falls back to the printed Spanish heading if SUGEF adds a category |
| License_Type | the Spanish subsection heading, title-cased |
| Cntry | `CR` |
| RegulationType | `Regulated` |
| RegCtry / RegCode / ListCode | `CR` / `SUGEF` / `1` |
| ListName | `Entidades Supervisadas` |
| ListLabel | `1` (see justification above) |
| ListLanguage | `ES` |
| ListValidityDate | parsed from `ACTUALIZADA AL <dd> DE <MES> DE <yyyy>` in the item-1 heading, falling back to the index anchor date. Both gave `2026-07-03`. |
| ListProcessDate | run date, `%Y-%m-%d` |

All other columns are `''`. Rows are appended through `add_row()`, which writes every fixed
field and then calls `bourange_same_length_array()` to pad all 42 columns, so columns cannot
drift out of alignment.

## Notes / QA

- **Run of 2026-08-20 produced 39 rows** from edition
  `actual/2026_03.pdf`, dated **03/07/2026** — the newest edition on the index page.
- The PDF prints a `(Total: n)` next to every subsection heading, so the script
  **self-reconciles** parsed vs declared counts and prints a loud warning banner on any
  mismatch:

| Subsection | Declared | Parsed |
|---|---|---|
| 1.1 Bancos Comerciales del Estado | 2 | 2 |
| 1.2 Bancos Creados por Leyes Especiales | 2 | 2 |
| 1.3 Bancos Privados | 10 | 10 |
| 1.4 Empresas Financieras No Bancarias | 4 | 4 |
| 1.5 Organizaciones Cooperativas de Ahorro y Crédito | 18 | 18 |
| 1.6 Asociaciones Mutualistas de Ahorro y Préstamo | 2 | 2 |
| 1.7 Otras Entidades Financieras | 1 | 1 |
| **Total** | **39** | **39** |

- **Layout support**: the current numbered-entry layout (name + cédula) starts with edition
  `2024_01` (08/04/2024). Verified parses: `2024_01` 44/44, `2024_05` 44/44, `2024_09`
  40/40 (the November 2024 edition the ticket cites), `2025_08` 39/39, `2026_03` 39/39.
  Editions `2023_09` and older use a two-column bullet (`•`) layout with no cédula and are
  **not** supported — the script would flag them via the total mismatch. This only matters if
  SUGEF ever reverts the layout, since the script always takes the newest edition.
- **Judgment call — former names.** Item 1 prints one entity as
  `Davibank (Costa Rica) S.A. (antes Scotiabank de Costa Rica S.A.)`. The trailing
  *(antes …)* clause is stripped so `Name` holds only the current legal name, which matches
  better downstream. Set `KEEP_FORMER_NAME = True` to keep the string exactly as printed.
- No address, phone, website or e-mail is published in item 1, so those columns stay empty.
