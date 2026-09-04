# AR BCRA — Banco Central de la República Argentina

**Jira:** DECD-6965
**Regulator:** Banco Central de la República Argentina (Argentine central bank)
**Entry point:** https://www.bcra.gob.ar/
**Version:** v1 (greenfield — no prior BCRA scraper existed in this repo)
**Last run:** 2026-09-02 → `AR BCRA SQL Ready 2026-09-02 23.36.46.xlsx`, **436 rows**, 8/8 lists at their measured counts

> The earlier file from the same day, `…23.31.01.xlsx`, is kept alongside it but is
> **superseded**: it shipped 20 list-3 rows whose `City` read `CABA ZONA NORTE` /
> `CABA ZONA SUR`. See quirk 6 below. The two files differ in the `City` column and
> nowhere else; row counts are identical.

---

## Lists

All eight lists come from the Jira description. Row counts are **observed** on 2026-09-02.

| ListCode | ListLabel | ListName | Source type | Rows |
|---|---|---|---|---|
| 1 | 1 | Financial Institutions | JSON API — list + 1 detail call per entity | 73 |
| 2 | 4 | Exchange Houses | JSON API | 7 |
| 3 | 4 | Interoperable e-wallets | JSON API | 91 |
| 4 | 4 | Public guarantee funds | static HTML table (**Spanish page**) | 17 |
| 5 | 4 | Platforms for MSME Financing | JSON embedded in the HTML | 7 |
| 6 | 4 | Payment service providers | JSON API, `tipoPSP=1` | 227 |
| 7 | 1 | Representatives of foreign financial institutions | static HTML table (**Spanish page**) | 8 |
| 8 | 4 | Electronic clearing houses / EFT scheme managers | hand-written `<ul><li>` | 6 |
| | | | **TOTAL** | **436** |

### Endpoints and selectors actually used

| # | Endpoint / selector |
|---|---|
| 1 | `api/endpoints/entidades-financieras.php?action=list&lang=en`, then `?action=detail&bco=<codigo>&lang=en` per entity |
| 2 | `api/endpoints/casas-de-cambio.php?lang=en` |
| 3 | `api/endpoints/billeteras.php?action=list&lang=en` |
| 4 | `https://www.bcra.gob.ar/fondos-de-garantia-de-caracter-publico/` → `table#tabla-rowcolspan-int` |
| 5 | ticket URL → `div#registro` (hidden), `json.loads` of its text → `result[]` |
| 6 | `api/endpoints/proveedores-psp.php?tipoPSP=1&lang=en` |
| 7 | `https://www.bcra.gob.ar/representantes-de-entidades-financieras-del-exterior/` → `table#tabla-rowcolspan-int` |
| 8 | ticket URL → `div.et_pb_text_3 .et_pb_text_inner ul li` |

`api.bcra.gob.ar` — the *documented* public BCRA API — is **not** usable here: it has no
entity register (`/entidades/...` 404) and its statistics routes now return `410 Gone`.
The real source is the website's own `www.bcra.gob.ar/api/endpoints/*.php`, which is what
each page's JavaScript calls. Only four such endpoints exist; lists 4, 5, 7 and 8 have
none and are parsed from HTML.

### Template fields (fixed — do not derive these at runtime)

```
RegCtry  = 'AR'      # 2-letter country code, not the country name
RegCode  = 'BCRA'    # the agency alone, not 'AR BCRA'
ListCode = '1'..'8'  # the bare ticket ListNr, not 'AR BCRA 1'
```

These are the three tokens of `<CC> <AGENCY> <listnr>` and are asserted before the file is
written. `RegulationType` is `'Regulated'` on all 436 rows; `ListProcessDate` is stamped
`datetime.datetime.now().strftime('%Y-%m-%d')` on every row.

### ListLabel reasoning

Rule: 1 = bank, 2 = insurance, 3 = both, 4 = everything else. Assigned per list, not
blanket-assigned:

- **List 1 → 1.** *Entidades financieras* is the bank register proper: commercial banks
  plus *compañías financieras*, all licensed under the Ley de Entidades Financieras.
- **List 7 → 1.** These are the licensed representative offices of foreign **banks**
  (Commerzbank, Deutsche Bank, Itaú Unibanco, Bank of America…), carried under the same
  supervisory regime as list 1.
- **Lists 2, 3, 4, 5, 6, 8 → 4.** Exchange houses, e-wallets, public guarantee funds,
  MSME financing platforms, payment service providers and clearing houses are all
  non-bank, non-insurance. BCRA is a central bank but it is *not* the case that every one
  of its registers is a bank list.

No list on this ticket is an insurance list — Argentine insurance is supervised by the SSN,
not the BCRA — so labels 2 and 3 do not occur.

---

## The /en/ pages are stale — lists 4 and 7 are scraped in Spanish

Measured 2026-09-02, both pages, same selector:

| List | Spanish page | English page (the ticket URL) |
|---|---|---|
| 4 Public guarantee funds | **17** rows | 16 rows |
| 7 Representatives of foreign FIs | **8** rows | 4 rows |

- List 4: the English page is missing entity **51017 — Fondo de Garantía Santa Fe Produce
  (FOGAFE)**.
- List 7: the English page carries 4 of the 8 entities, and corrupts one code cell into
  the literal text `Item No. 30013`.

Dropping real regulated entities because a translation lagged is not acceptable, so these
two lists are taken from the Spanish pages and `ListLanguage` is set to `ES` for them.
The scraper still fetches the English page for list 4 each run — not for data, but to read
the column labels (the Spanish table ships **no header row at all**) and to print which
entity codes are Spanish-only. Every other list uses the ticket's own `/en/` URL.

**If the requester QAs by counting rows on the English page they will see 16 and 4, not 17
and 8.** That difference is intentional.

### CONFIRMED by the ticket owner, 2026-09-02: take the most current page, whichever language

Re-measured live the same day, independently, counting `<tr>` elements that contain a `<td>`
(a cruder count than the parser's — it picks up one extra structural row per table, so read
the *difference*, not the absolute):

| Source | EN | ES | scraped |
|---|---|---|---|
| List 4 `/public-guarantee-funds/` vs `/fondos-de-garantia-de-caracter-publico/` | 17 | **18** | ES |
| List 7 `/representatives-of-foreign-financial-institutions/` vs `/representantes-…-del-exterior/` | 4 | **8** | ES |
| Lists 1, 2 (`entidades-financieras.php`, `casas-de-cambio.php`) | 73, 7 | 73, 7 | API, `lang=en` |
| Lists 3, 6 (`billeteras.php`, `proveedores-psp.php`) | one dataset, `lang` only relabels it | | API, `lang=en` |
| Lists 5, 8 | only an English page exists (the Spanish slugs 404) | — | EN |

So every list is already taken from its most current source and **no code change was needed**:
Spanish where Spanish is ahead, the API where language is only a label, English where English
is all there is.

### Re-confirmed 2026-09-03 after a "why 8 and not 4?" query — decision unchanged

The 8 vs 4 on list 7 was queried again. Both pages were re-fetched live and diffed row by
row. The four extra rows are **distinct entities with distinct BCRA codes**, present only on
the Spanish page — not duplicates, not parser artefacts:

| Code | Entity represented | On the /en/ page? |
|---|---|---|
| 30004 | Commerzbank Aktiengesellschaft | yes |
| 30013 | Deutsche Bank AG | yes |
| 30154 | Itaú Unibanco S.A. | yes |
| 30365 | Bank of America, National Association | yes |
| 30403 | Crédit Agricole Corporate and Investment Bank | **no — ES only** |
| 30454 | Standard Chartered Bank | **no — ES only** |
| 30650 | Coöperatieve Rabobank UA | **no — ES only** |
| 30701 | Banco Latinoamericano de Comercio Exterior, S.A. | **no — ES only** |

Further evidence that the English table is an old snapshot rather than a translation of the
current one — it disagrees with Spanish on rows it *does* carry:

- Deutsche Bank domicile: EN `Sarmiento 212, 9th Floor, Of. B2` vs ES `Ortíz de Ocampo 3302,
  Módulo 2, Oficina 9`.
- Bank of America domicile: EN `Carlos M. Della Paolera 265, 11th floor` vs ES
  `Carlos M. Della Paolera 261, piso 20`.
- The EN representative columns are **shifted**: Bank of America's alternate-representative
  cell holds two people run together (`Bocardi, Verónca Andrea Antonini, Diego Glauco`),
  which Spanish correctly splits into titular = Bocardi, alternate = Antonini.
- Plus the already-known `Item No. 30013` corruption in the code cell.

**No independent confirmation exists.** `entidades-financieras.php?action=detail` returns
`Entidad no encontrada` for 30403 / 30454 / 30650 / 30701 — but it returns the same for
**30013**, which is on *both* pages, so that endpoint simply does not cover representative
offices and is not evidence either way. Neither page publishes a last-updated date.

Ticket owner confirmed again on 2026-09-03: **keep Spanish, 8 and 17.** ES membership is a
strict superset of EN in both lists, so nothing on the English page is lost by this choice.

---

## Site quirks (things that will break this later)

1. **Nothing is in the rendered HTML for lists 1, 2, 3, 6.** The pages contain no table,
   no `<select>`, not one `<option>`. Everything is drawn client-side from the PHP
   endpoints above. `?bco=00340` on the list-1 page returns HTTP 200 with no entity data
   in it. Do not try to parse those pages; call the endpoint.
2. **List 1's "click on search" is an XHR.** The ticket says *"select each company …
   click on search and extract the information of each"*. That click is
   `action=detail&bco=<codigo>`, so the scraper issues 73 detail calls. No browser needed.
3. **`<br>` inside JSON address strings.** `billeteras` (54 of 91 rows) and
   `proveedores-psp` (227 of 227) embed a literal `<br>` separating the street from a
   repeat of city/postcode/province. Only the part before it belongs in `Address_1`.
4. **Composite address strings.** Exchange houses give
   `Calle y N°: Mitre 868, P.B., Santa Fe, ROSARIO (CP: S2000COR)` — the label prefix, the
   province, the city and the postcode all repeat data that has its own column.
   `street_only()` peels the tail off using the row's own values.
5. **List 1 addresses are `STREET - LOCALITY - PROVINCE`**, and all 73 split into exactly
   three segments. A row that does not is kept whole rather than guessed at.
6. **The locality is sometimes a BCRA supervision zone, not a city — on more than one
   list.** `CABA ZONA NORTE` / `CABA ZONA SUR` is an internal supervisory division, not
   part of the address. It leaks from two independent source fields:

   | List | Source field | Rows affected |
   |---|---|---|
   | 1 | middle segment of `direccion` | 42 of 73 |
   | 3 | `domicilio.localidad` | 20 of 91 |

   `strip_zona()` trims it back to the city it qualifies (`CABA`); provincial entities
   (`SANTO TOME`, `VICENTE LÓPEZ`, `ROSARIO`) are untouched. **The normalisation is applied
   centrally in `emit()`, so it covers every list — including any added later.** It was
   originally patched at list 1's call site only, which shipped list 3 dirty in the
   `23.31.01` file; an assertion now fails the run if any list leaks a zone into `City`.
   The 20 list-3 rows are all central Buenos Aires banks (BBVA, Macro, Nación, Patagonia,
   Galicia, Santander, Uala Bank, …), so `CABA` is correct for every one of them.

   Note this fixes only the *zone suffix*. List 3's `City` is inconsistent at source in
   other ways that are **not** normalised, because collapsing them would be inventing
   data: `CABA`, `Capital Federal`, `C.A.B.A.`, `CAPITAL FEDERAL`, `Ciudad Autónoma de
   Buenos Aires`, `Ciudad de Buenos Aires` all appear and all refer to the same city.
   **CONFIRMED by the ticket owner 2026-09-02: leave them exactly as the site publishes
   them.** The zone suffix is a different case and is still stripped — `ZONA NORTE` /
   `ZONA SUR` is BCRA's own supervisory division, not part of any city's name, so it is
   removed rather than unified. Everything that is genuinely a spelling of the city stays
   verbatim.
7. **List 5's table is an empty shell.** The visible `<table>` has headers and no rows; the
   data is server-rendered as JSON inside `div#registro[hidden]` on the same response.
8. **List 8 has no table.** Its two `table#tabla-rowcolspan-int` elements are decoys with
   no cells; the data is two hand-written `<ul>`s. Every `<li>` starts with an en dash
   (U+2013) that must be stripped. Its section headings are **Spanish even on the /en/
   page**.
9. **All-digit identifiers arrive as JSON ints** (`cuit: 30715084291`,
   `telefono: 1152635263`) while list 1's detail returns them formatted
   (`30-70722741-5`). Everything is forced to text end-to-end.
10. **Encoding is clean.** Every page and endpoint is genuinely UTF-8; the 2026-09-02 run
    produced zero mojibake markers. No `verify=True` though — the corporate proxy needs
    `verify=False` plus `ssl._create_default_https_context = ssl._create_unverified_context`.

---

## Field mapping

Common to every row: `Cntry='AR'`, `RegulationType='Regulated'`, `RegCtry`/`RegCode`/
`ListCode`/`ListName`/`ListLabel`/`ListLanguage`/`ListProcessDate` from the list spec,
`Typology = ListName`.

| List | Name | InternalID_1 (`_type`) | InternalID_2 | CoType | License_Type | Address_1 / Address_2 / City / Zip |
|---|---|---|---|---|---|---|
| 1 | `nombre` | `codigo` (BCRA entity code) | `cuit` (CUIT) | `grupo_institucional` | `tipo` | street / province / locality / — |
| 2 | `denominacion` | `codigo_externo` (BCRA registration number) | — | `Exchange House` | suspension, if any | street / `provincia` / `localidad` / `codigo_postal` |
| 3 | `denominacion_pj` | `codigo_billetera` (E-wallet code) | `cuit` | `Interoperable e-wallet` | VQR enabled / not | as above |
| 4 | col *Denomination* | col *Code* | col *Tax id number* | `Public guarantee fund` | — | *Domicile* / *Province* / *City* / *Zip code* |
| 5 | `TX_DENOMINACION_PJ` | `CD_CODIGO_ENTIDAD` (Platform code) | `CD_CUIT` | `Platform for MSME financing` | — | direction + floor / province / locality / CP |
| 6 | `denominacion_pj` | `codigo` (Provider code) | `cuit` | `Payment service provider` | `tipo_psp_nombre` | as above |
| 7 | *Entidad representada* | *Código entidad* | — | Representative office of a foreign FI | — | *Domicilio* / — / *Localidad* / — |
| 8 | `<li>` text | — | — | group heading (CEC / EFT scheme manager) | — | — (site gives names only) |

Also: list 1 fills `Phone`, `Fax`, `Website`, `Email` and `EntryType='Head Office'`;
list 3 fills `Website`; list 7 fills `EntryType='Representative Office'`,
`Name - Mother Company` and `Cntry - Mother company`.

`ListValidityDate` is set on **list 1 only**, from the register's own
`fecha_actualizacion` stamp (*"mayo de 2026"* → `2026-05-01`). BCRA publishes month
granularity only, so **the day is synthetic**. No other list declares a validity date.

### List 7 — how the row is shaped

The named entity is a **foreign** bank, but the address and phone belong to its
**representative office in Argentina**. So `Cntry` follows the address (`AR`) and the home
jurisdiction is carried separately:

```
Name                    = Commerzbank Aktiengesellschaft
Cntry                   = AR          # the rep office is in Buenos Aires
Name - Mother Company   = Commerzbank Aktiengesellschaft
Cntry - Mother company  = DE          # mapped from 'Alemania'
```

Country names come back in Spanish (`Alemania`, `Gran Bretaña`, `Países Bajos`,
`Estados Unidos de América`, …) and are mapped to ISO alpha-2 by `CNTRY_ES`. An unmapped
name is reported loudly and left blank rather than guessed.

---

## Deliberate omissions (ask the requester if these are wanted)

The 43-key `sqldict` is fixed and none of its fields means "trade name" or "contact
person", so rather than overload a column with something it does not mean, these source
fields are **not** emitted. Each is a one-line change to add:

1. **Commercial/trade name** — `marca_comercial` (list 3), `TX_MARCA_COMERCIAL` (list 5),
   `denominacion` (list 6). The ticket explicitly says to use *"Name of legal person"* as
   `Name` for list 3, which is what is done.
   *This matters for four list-3 rows*: the brand is the only human-readable thing telling
   them apart —
   `BANCO DE LA PROVINCIA DE CORDOBA SA` appears as **BANCON** (36513) and **BEZZA**
   (36584); `BANCO DE LA CIUDAD DE BUENOS AIRES` as **Banco Ciudad** (36518) and
   **Buepp** (36554). They are four distinct registrations and `InternalID_1` separates
   them, but on `Name` alone they read as duplicates.
2. **Representative persons** (list 7) — *Representante titular* and *Representante
   suplente*, two people per row.
3. **Banking-association membership** (list 1) — `asociado_1` / `asociado_2` (`ABA`,
   `ABAPPRA`, `ABE`, `ADEBA`, `AFIMA`). These are trade-association memberships, not a
   parent company, so `Name - Mother Company` would be wrong.
4. **Ratings** (list 1) — `calificaciones[]` and `fecha_evaluacion`.

---

## Judgment calls for the requester

1. ~~**Lists 4 and 7 are scraped from the Spanish pages**~~ — **CONFIRMED 2026-09-02**: take
   the most current page whatever its language. Lists 4 and 7 stay on Spanish (17 and 8 rows);
   counting rows on the ticket's own English URLs gives 16 and 4. See the section above.
2. ~~**List 6 is `tipoPSP=1` only — 227 rows.**~~ — **CONFIRMED 2026-09-02: 227 is what is
   wanted.** The ticket URL pins that query string. For the record, the same endpoint serves
   eight further PSP types totalling ~210 more entities: 2 Initiator 5, 3 ATM Network 5,
   4 EFT Network 3, 5 Acceptor 64, 6 Acquirer 15, 7 Aggregator 91, 8 Non-bank Collection 23,
   9 QR Administrator 4. If they are ever wanted, the list goes 227 → 437 and the file total
   436 → 646; it is a loop over `tipoPSP` in `LISTS[6]['url']`.
3. **Nothing is deduped.** 436 is what the site shows.
   - List 8 legitimately lists *Compensadora Electrónica SA* and *Interbanking SA* under
     **both** group headings (6 `<li>` rows, 4 distinct names). The group is the only thing
     separating the two entries, so both are kept.
   - List 6 contains a genuine duplicate in BCRA's own data: **GROW SOLUTIONS SA / G-PAGOS
     appears twice under the same provider code 33786**, differing only in the letter case
     of its locality. The site returns 227 including it, so the file has 227.
4. **`Website` is 37% populated overall** — only lists 1 and 3 publish a website column at
   all. Lists 2, 4, 5, 6, 7, 8 have no such field on the source. This is not a scrape gap.

---

## Built-in checks

The run fails loudly rather than shipping a bad file:

- 43-key schema asserted at import **and** the DataFrame's columns asserted against it.
- `add_row()` is the only writer; it raises on an unknown key and on column desync.
- `RegCtry` / `RegCode` asserted to single fixed values; `ListCode` asserted all-numeric;
  `ListLabel` asserted within {1,2,3,4}; `RegulationType` and `ListProcessDate` asserted
  present on every row.
- **`Name` content** asserted separately from the row count — a row count of 436 does not
  prove `Name` holds names (a sibling regulator once shipped 997 reconciled rows with
  `Yes`/`No` in `Name`).
- **`City` content** asserted across **every** list: the run aborts if any row leaks a
  `ZONA` supervision suffix into `City`. Added after the first `23.31.01` file shipped
  with list 1 clean and list 3 dirty — a per-list spot check had passed while the file was
  still wrong, so the check is now file-wide and reports the offending ListCodes.
- List 4's column order is cross-checked against the English page's header labels, and each
  row's CUIT column is regex-checked; list 7's columns are mapped **by label**, not by
  position.
- Endpoint-declared totals (`total`) reconciled against parsed row counts for lists 2, 3, 6.
- Per-list row counts compared against the 2026-09-02 measurements; drift **warns**, it does
  not abort — a regulator adding or removing an entity is legitimate.
- **Excel round-trip**: `InternalID_*`, `Zip`, `Phone`, `Fax` are pinned to text, the
  workbook is read back, and scientific notation / lost leading zeros are asserted against.
  This is not theoretical — 98 rows carry a phone like `000043294201`, and CUITs arrive as
  11-digit ints.

### QA of the 2026-09-02 run (no `qa_positive_combined/` baseline exists for AR BCRA)

Required-field non-empty rates: `Name` 100%, `Cntry` 100%, `InternalID_1` 99%,
`City` 98%, `Address_1` 98%, `Phone` 97%, `Website` 37%.
Encoding red flags (`Ã`, `â€`, `Â`, `?{3,}`, stray `<br>`, HTML entities, U+FFFD): **0**.
Every shortfall was traced to the source, not to the parser:

- `InternalID_1` 99% → list 8 (6 rows) has no codes on the site.
- `City`/`Address_1` 98% → list 8, plus two list-3 rows whose `domicilio` object is empty
  at source (HSBC BANK ARGENTINA 36526, BANCO ITAU ARGENTINA 36528).
- `Phone` 97% → list 8; one list-4 fund (Garantía San Juan) and two list-7 rows
  (Deutsche Bank AG, Itaú Unibanco) have a blank phone cell on the site.

---

## Running

```bash
# from the repo root
.venv/bin/python "AR BCRA/AR_BCRA_v1.py"
```

`AR_BCRA_v1.ipynb` is the same code split at the `#---- Begin_… ----` markers. Output
lands in **this folder** (not `tempfolder/`) as
`AR BCRA SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, sheet `SQL Ready`.

Runtime is a couple of minutes and is dominated by list 1's 73 sequential detail calls.
No browser, no Selenium, no DrissionPage — every one of the eight sources answers a plain
`requests.get` with HTTP 200. No Cloudflare, no 403.

Nothing is printed from the pages themselves: the Windows control server console is cp1252
and raises `UnicodeEncodeError` on Spanish accented characters, so all diagnostics go
through `ascii_slug()` and are counts rather than content.

### Translation

None is applied and `googletrans` is **not** imported. `Name` stays in the original
Spanish, as required. The only Spanish→English conversions are closed enumerations
hard-mapped in code — three `tipo` values, seven country names, two list-8 group headings —
which is more reliable than machine translation over a set this small. Source classification
values (`grupo_institucional`, `tipo`) are kept verbatim rather than invented in English.
