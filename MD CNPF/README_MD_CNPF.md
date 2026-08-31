# MD CNPF — Comisia Națională a Pieței Financiare (Moldova)

Jira: **DECD-6827**  ·  Scraper: `MD_CNPF_v3.py` / `MD_CNPF_v3.ipynb`
Hub page (single source for all 8 lists): <https://www.cnpf.md/ro/registrele-actelor-permisive-6412.html>

CNPF is Moldova's **non-bank** financial supervisor (capital market, crowdfunding, trust
companies, pensions). Banks are supervised by BNM — see the sibling folder `MD NBMO`.

## Lists

All eight lists live behind eight `<button class="accordion">` blocks on the single hub page
above. Every register is a **downloadable file**, not HTML.

| ListNr | ListCode | ListLabel | ListName | Source type | Rows |
|---|---|---|---|---|---|
| 1 | `1` | 4 | Companies licensed or authorized on the capital market | PDF, 8 pages | **33** |
| 2 | `2` | 4 | Authorized companies in the stock market | DOCX, 2 tables | **5** |
| 3 | `3` | 4 | Register of crowdfunding service providers | XLSX | **2** |
| 4 | `4` | 4 | Entities holding information on securities holders | PDF, 2 pages | **29** |
| 5 | `5` | 4 | Issuers of securities with register-keeping contracts | XLSX, 2 sheets | **1038** |
| 6 | `6` | 4 | Issuers whose shares are kept by the Central Single Depository | XLSX | **187** |
| 7 | `7` | 4 | Investment funds reorganized into joint-stock companies | **.doc (Word 97-2003)** | **7** |
| 8 | `8` | 4 | Trust companies | **.doc (Word 97-2003)** | **6** |
| | | | | **TOTAL** | **1307** |

Row counts above are from the real run of 2026-08-20 that produced
`MD CNPF SQL Ready 2026-08-20 18.56.18.xlsx`.

### ListLabel justification

`1` = bank, `2` = insurance, `3` = bank & insurance, `4` = everything else.

**Every CNPF list here is `4`.** None of these eight registers is a banking or an insurance
licence register. They are capital-market registers (investment firms, registrars, investment
consultants, pension-fund administrators), crowdfunding providers, share-valuation experts,
securities issuers and trust companies. Banks do appear *inside* lists 1, 5 and 6 — e.g.
`Banca Comercială MAIB SA` holds a category-C **investment-firm** licence in list 1, and list 6
has an explicit `BĂNCI` section — but they are listed there in a capital-market capacity, not
as licensed banks. ListLabel is assigned per list, not per row, so `4` is correct for all eight.
Their banking licences are covered by MD NBMO list 1.

### RegulationType

Most rows are `Regulated`. Three lists are not uniformly positive, and the source itself
separates them:

| Rows | RegulationType | Why |
|---|---|---|
| 22 (list 1) | `Regulated` | Active licences/authorisations |
| 11 (list 1) | `Withdrawn` | Pages 6-7 of the list-1 PDF are headed *"LISTA PERSOANELOR LICENȚIATE SAU AUTORIZATE CĂRORA LE-AU FOST RETRASE LICENȚELE/AUTORIZAȚIILE, DAR CARE NU AU FOST RADIATE DIN REGISTRELE CNPF"* — licence withdrawn, but not yet struck off the register |
| 4 (list 2) | `Regulated` | Table 1 of the DOCX — authorised share valuers |
| 1 (list 2) | `Withdrawn` | Table 2 of the DOCX, headed *"Lista persoanelor cărora le-a fost retrasă calitatea…"*; `RegulationDate` = authorisation decision, `CancellationDate` = withdrawal decision |
| 18 (list 4) | `Regulated` | Page 1 — registrars + issuers self-keeping their registers |
| 11 (list 4) | `Withdrawn` | Page 2, same "RETRASE" heading as above |
| 6 (list 8) | `In liquidation` | **Every** trust company in the file is annotated `– în proces de lichidare a genului de activitate`. None is a normal going concern. Flagged below as a judgment call. |

## Field mapping

Common to all rows: `RegCtry='MD'`, `RegCode='CNPF'`, `Cntry='MD'`, `ListLanguage='RO'`,
`ListProcessDate` = run date. `ListValidityDate` is filled only where the file stamps its own
date (lists 1, 3, 4 — see reconciliation).

| List | Name | InternalID_1 | InternalID_2 | Other |
|---|---|---|---|---|
| 1 | `Denumirea` | IDNO | licence number (`CNPF 000891`) | `CoType` = section banner (OPERATOR DE PIAŢĂ / SOCIETĂȚI DE INVESTIȚII / CONSULTANȚI DE INVESTIȚII / ADMINISTRATORI AI FONDURILOR DE PENSII / SOCIETĂȚI DE REGISTRU); `License_Type` = all licence rows joined with ` \| `; `RegulationDate` = licence issue date; address/phone/fax/e-mail/web parsed out of the combined `IDNO/adresă/contact` column |
| 2 | `Denumirea` | IDNO (`Codul fiscal`) | certificate number (`seria SPVM nr. …`) | `RegulationDate` from the CNPF authorisation decision |
| 3 | `Denumirea completă` (trimmed before `Denumirea prescurtată/comercială`) | IDNO | CNPF decision number | `CoType` = `Forma juridică`; e-mail/website matched across the whole row (see quirk 4) |
| 4 | `Denumirea` | IDNO where present | — | `CoType` = the ALL-CAPS section heading from the page text (`SOCIETĂŢI DE REGISTRU`); phone/fax/e-mail from the contact columns |
| 5 | `Denumirea societatii pe actiuni` | IDNO | **ISIN** | `License_Type` = `Contract de tinere a registrului cu <registrar>`; `CoType='SA'` |
| 6 | `Denumirea societatii pe actiuni` | IDNO | — | `CoType` = section banner (`BĂNCI` / `SOCIETĂȚI DE ASIGURĂRI` / `ALȚI EMITENȚI`) |
| 7 | **new** name (`Denumirea nouă`, IDNO stripped) | IDNO | — | `License_Type` carries the **former** fund name (`denumirea veche: F.I.N.N. «Mandatar»`) |
| 8 | `Denumirea` with the `– în proces de lichidare` suffix stripped | — | — | `CoType='Companie fiduciara'`, `License_Type='Administrator fiduciar'` |

## Row-count reconciliation

Four of the eight sources declare their own count via a `Nr.` column; the scraper parses it and
prints scraped-vs-declared. **All four match exactly** in the run above:

```
list 1  rows=  33   (matches source-declared 33)   validity=2026-06-29
list 4  rows=  29   (matches source-declared 29)   validity=2026-03-01
list 5  rows=1038   (matches source-declared 1038)
list 6  rows= 187   (matches source-declared 187)
```

Lists 2, 3, 7 and 8 have no usable `Nr.` sequence; their counts (5 / 2 / 7 / 6) were checked by
eye against the source tables.

**The declared count is a SUM, not a maximum.** Lists 1, 4 and 6 restart their `Nr.` numbering
under every section banner. Taking the last number on the sheet would have declared 12 for
list 1 (actual 33) and 167 for list 6 (actual 187). The scraper sums per-section maxima.

No deduplication is performed anywhere. If an entity appears in more than one list — banks
appear in lists 1, 5 and 6 — it legitimately gets one row per list.

## Site quirks (things that will break this scraper later)

1. **File names rot constantly.** The current list-1 file is literally
   `LISTA Participanti la situatia din 10_03_2026 (1)(1)(1).pdf`. CNPF re-uploads and the
   `(1)(1)(1)` suffix grows. Nothing is hard-coded: the scraper resolves the accordion by its
   **label text** and then the anchor by its **label text**, every run. If a label changes it
   prints a loud `SKIPPED — no accordion whose label contains '<keyword>'` rather than silently
   yielding 0 rows. **This is the single most likely future breakage** — CNPF rewording an
   accordion heading. Keywords live in `ACCORDIONS` / `ANCHORS` at the top of the file.
2. **Two accordions hold more than one file.** Accordion 4 also links the DCU's own contact PDF
   on `dcu.md`; accordion 7 holds both *funds in liquidation* and *funds reorganized into
   joint-stock companies*. The ticket asks for the second one in accordion 7 and the first in
   accordion 4, so `ANCHORS` disambiguates by label substring.
3. **Mixed Romanian diacritics.** The page mixes the correct comma-below `ș`/`ț` (U+0219/U+021B)
   with the Turkish cedilla `ş`/`ţ` (U+015F/U+0163). They look identical and are different
   codepoints. All label matching goes through `norm()` (NFKD + strip combining marks + lower),
   never `==`.
4. **The crowdfunding XLSX data rows are shifted against their own header** from the e-mail
   column onward, because of a merged cell. Fixed column indices silently returned blank
   e-mail/website. E-mail and website are now matched by pattern across the whole row.
5. **A section banner can be invisible to the table parser.** In the list-1 PDF, pdfplumber
   never emits the "…RETRASE LICENȚELE…" banner as a table row — the `Nr.` column just silently
   restarts at 1 on page 6. The scraper reads that banner from the **page text** and treats a
   numbering restart as a new section. Without this, 11 withdrawn entities were being written
   as `Regulated`.
6. **Legacy short fiscal codes exist.** `SA "COMPANIA BUGEAC"` is filed under the 5-digit code
   `64096`, and several list-5 entries have 12-digit IDNOs. A 13-digit-only IDNO rule dropped
   these rows.
7. **A data row may contain the word `Denumirea`.** The generic `is_header_row()` helper matched
   a real list-7 entity and dropped it. Any row containing a long digit run is now never a header.
8. **List 5's workbook has a second sheet** (`CONTRACTE REZILIATE ANULATE`, 361 rows) of
   terminated contracts. The sheet is discovered by name (`activ`), never by position, and the
   scraper logs the other sheet's size instead of silently ignoring it.

## What was wrong with v1 / v2, and what changed

Both prior notebooks are unrunnable on the production control server. They are left in place
untouched; v3 is a rewrite.

| Defect in v1 / v2 | v3 |
|---|---|
| **`import win32com.client as win32`** — Windows COM / MS Word automation. The control server has no Office, no Word, no Excel and no COM. This is what `_needwin32` in the v1 filename refers to. | Removed. Legacy `.doc` files are read by a **pure-Python OLE2/CFB reader** (`_cfb_streams` / `doc_text` / `doc_table`) lifted from `MD NBMO/MD_NBMO_v2.py`. Verified working on both CNPF `.doc` files. |
| **Selenium + ChromeDriver** used to download every file, and `driver.maximize_window()` requires a display. | Removed. Plain `requests` fetches the hub and all 8 files. |
| **`Page.printToPDF` against `view.officeapps.live.com`** — v2 round-tripped a `.doc` through Microsoft's public Office web viewer to get a PDF, then OCR-free parsed it. External dependency on a Microsoft service, and it leaks the target URL. | Removed entirely; the `.doc` is parsed directly. |
| **Hard-coded absolute Windows path** `C:\Users\wuj1\OneDrive - Moody's\Desktop\Regulator\MD CNPF`. | `os.path.dirname(os.path.abspath(__file__))` with a notebook fallback. |
| **Hard-coded file URL** for the 2017 funds `.doc`, and a hard-coded `if idx != 6:` special case keyed on loop position. | Every URL resolved from the hub page by label each run. |
| **44-key `sqldict`** — it carried an extra `'Check'` column, which fails QA on schema alone. | Exactly the **43** canonical keys. Asserted at the end of the run (`len(sqldict) == 43`). |
| **`bourange_same_length_array()`** back-filled short columns with `''` *after the fact*, so a parser that wrote 5 of 43 fields silently misaligned the rest. | A single `add_row(**kw)` writes **all 43 columns on every record** and raises `KeyError` on an unknown column name. Column-length drift is asserted impossible. |
| No `ListProcessDate`, `RegulationType`, `ListLabel`, `ListValidityDate` population. | All populated; `ListValidityDate` parsed out of the files that stamp it. |
| Output written with `df.to_excel(filename)` and no sheet name; v2 never filtered blank names. | `sheet_name='SQL Ready'`, written to the regulator folder, `df[df['Name'] != '']`. |
| No reconciliation, no soft-404 check. | Scraped-vs-declared printed per list; every download asserts real `%PDF` / `PK` / OLE2 magic bytes before parsing. |

## Judgment calls for the requester

1. **List 8 `RegulationType = 'In liquidation'`.** All six trust companies carry
   `– în proces de lichidare a genului de activitate` in the source. I did not force these to
   `Regulated`. Confirm the desired value (`Regulated`? `In liquidation`? excluded entirely?).
2. **Withdrawn entities inside lists 1, 2 and 4 were kept**, with `RegulationType='Withdrawn'`
   (22 rows total). The ticket says "extract all entities from the file"; each file contains a
   positive register *and* a withdrawn/retired block under a separate heading. Excluding them
   would drop list 1 from 33 to 22 and list 4 from 29 to 18. Confirm keep-or-drop.
3. **List 5: only the `CONTRACTE ACTIVE` sheet is scraped** (1038 rows). The workbook's second
   sheet, `CONTRACTE REZILIATE ANULATE`, holds 361 terminated contracts. The ListName says
   *"…that have concluded register keeping contracts…"*, which reads as active. Confirm whether
   the 361 terminated ones should be added with a `CancellationDate`.
4. **List 7 `Name` = the NEW joint-stock company name** (e.g. `SA" JLC - Invest"`), because the
   IDNO in the source belongs to the new entity. The former fund name
   (`F.I.N.N. «Mandatar»`) is preserved in `License_Type`. Confirm which name should be primary —
   the schema has no "former name" field.
5. **The registrar company in list 5** (`Societatea de Registru`, e.g. `GRUPA FINANCIARĂ`) is
   recorded inside `License_Type` text. It was deliberately **not** written to
   `Name - Mother Company`: a registrar is not a parent undertaking and populating that field
   would assert an ownership relationship that does not exist. Confirm if a different mapping
   is wanted.
6. **List 3's `Starea persoanei juridice` column** (`Activă`) is currently **not mapped** to any
   of the 43 fields. Both current providers are `Activă`. Confirm whether that status should
   drive `RegulationType`.
7. **`ListValidityDate` is blank for lists 2, 5, 6, 7, 8** because those files carry no
   "updated at" stamp. List 5's file name says `11_08_2026` and list 6's says `01_2024`, but
   **file names are not trustworthy as validity dates** here (the list-1 file is named
   `10_03_2026` while its own text says `la situația 29.06.2026`), so I did not derive dates
   from file names. Confirm whether the requester wants the file-name date as a fallback.

## Not verified

- The **English** side of the site (`/en/…`) was never fetched. MD NBMO had a trap where the
  English page linked a stale file; whether CNPF's English page links the same or different
  files is **unknown**. All eight registers were taken from the Romanian page, and
  `ListLanguage` is set to `RO` accordingly.
- Entity **names were not translated** to English; they are kept as published (Romanian).
- No comparison against a previous QA baseline was run (no `qa_positive_combined` baseline
  exists for MD CNPF).
