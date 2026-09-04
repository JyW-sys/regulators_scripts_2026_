# BI BRB — Banque de la République du Burundi

Jira: **DECD-6976**
Site: https://www.brb.bi (French, Drupal)
Scraper: `BI_BRB_v3.py` / `BI_BRB_v3.ipynb`
Run observed: 2026-09-03 — **114 rows total**, output `BI BRB SQL Ready 2026-09-03 12.27.53.xlsx`

The BRB is Burundi's central bank and the single supervisor for banks, financial
establishments, microfinance institutions and payment institutions. All three lists in this
ticket are positive registers of currently licensed entities.

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows (observed) |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | List of "Banking Supervision" | https://www.brb.bi/node/119 | static HTML, free-text `<p>` blocks | 17 |
| 2 | 2 | 4 | List of "Microfinance Supervision" | https://www.brb.bi/node/120 | **12 scanned PNG images** — OCR | 85 |
| 3 | 3 | 4 | List of "Payment Systems" | https://www.brb.bi/node/2928 | static HTML `<table>` | 12 |
| | | | | | **TOTAL** | **114** |

All three ticket URLs returned HTTP 200 on 2026-09-03 (`node/119` 78519 bytes / 176 `<p>` /
0 tables; `node/120` 70829 bytes / 0 `<p>` / **12 `<img>`**; `node/2928` 73294 bytes / 2
tables). **A re-platform *was* found — see "List 2 is no longer text" below.**

### ListLabel justification (1 = bank, 2 = insurance, 3 = both, 4 = other)

- **List 1 = 1** — the central bank, 15 commercial banks and 1 *établissement financier*
  (BNDE). A banking register in the plain sense.
- **List 2 = 4** — microfinance institutions. Follows the KH NBC / TJ NBTAJ precedent of
  classifying microfinance registers as `4`. **FLAGGED — see judgment call 1.**
- **List 3 = 4** — money-transfer operators, e-money issuers and payment aggregators.
  Neither banks nor insurers.

`RegulationType = 'Regulated'` on all 114 rows. The BRB does publish a *non-actifs* register
(suspended / licence-withdrawn payment institutions, the second table on `node/2928`), and
that table is **deliberately not scraped** — see judgment call 4.

---

## Site mechanics and quirks

No browser is needed anywhere. Plain `requests` + BeautifulSoup reaches all three pages;
`verify=False` is set because the dev Mac sits behind a corporate TLS proxy, and
`urllib3` warnings are silenced. There is no Cloudflare, no JS gate and no pagination.
Every page's content lives in `section#block-solo-content`, and each parser raises loudly
if that section is missing rather than returning 0 rows.

### List 2 is no longer text — it is a set of scans

This is the whole difficulty of this regulator. `node/120` used to carry the microfinance
register as `<p>` paragraphs (that is what `BI_BRB_v2.ipynb` parses). It now carries **zero
`<p>` elements and twelve `<img>` PNGs** — photographs/scans of a printed table. No PDF or
text-layer alternative was found on the site.

The pipeline is therefore:

1. **Collect** the 12 `<img>` sources from the content section (discovered per run, never
   hard-coded) and download them to `tempfolder/`.
2. **Split each PNG into printed pages** (`split_pages`). Several of the images stack more
   than one printed page into a single tall PNG — `image_4` is 2246 × 6440. Feeding that to
   the OCR downscales it so hard that the text degrades badly (observed garbage:
   `Ccuoratdiv`, `Suetele`, `Cuopérative` where the source says `Société Coopérative`).
   Each PNG is cut at its blank page-break bands: rows with essentially no dark pixels,
   runs of **≥ 100 px** only, cut at the run's midpoint. 12 images → **26 pages**.
   *A boundary is only kept if it leaves ≥ 400 px behind it, and a short leftover band is
   merged into its neighbour rather than dropped* — an earlier version discarded short
   segments outright and silently ate the category-4 heading with them.
3. **Read the table geometry** with `img2table` (OpenCV ruled-line detection) and the cell
   text with the OCR engine `resolve_ocr()` picked for this machine (see below).
   `img2table` occasionally misses the topmost table on
   a page whose first ruling line is close to the margin, so `page_tables()` makes a second
   pass on the image cropped 80 px above the first full-width horizontal line
   (`topmost_hline`) and adds any table whose y-band the first pass did not already cover.
4. **Find the category headings** with a separate full-page text OCR pass
   (`page_headings`). OCR splits a long heading across boxes, so `_ocr_lines()` regroups
   detection boxes into lines by y-overlap before matching, and the matcher looks one line
   ahead for the ordinal (`première`/`deuxième`/`troisième`/`quatrième`).
5. **Interleave** headings and tables by y-coordinate on each page, so a table is attributed
   to the heading physically above it.

### OCR engine selection — Tesseract first, RapidOCR only as a fallback

`resolve_ocr()` is the single place the engine is chosen, and both halves of the OCR
(table cell text and the heading pass) come from it:

| Machine | `shutil.which('tesseract')` | Table OCR | Text OCR |
|---|---|---|---|
| Windows control server | found (repo bundles `Tesseract-OCR/`) | `img2table.ocr.TesseractOCR(lang='fra')` | `tesseract … tsv` via `subprocess` |
| Dev Mac (no brew, no admin) | not found | `img2table.ocr.RapidOCR` | `rapidocr.RapidOCR` |

**Tesseract is the authoritative engine.** RapidOCR exists only so the script can be
developed on a machine with no `tesseract` binary; a RapidOCR run prints a `[WARN]` saying
its output is a dev run.

**The RapidOCR imports must stay inside the `else` branch.** The first build of v3 was
written Mac-first and imported them unconditionally at the top of `parse_list2()`. That
died on the control server:

```
File "...\BI-BRB\BI-BRB.py", line 678, in parse_list2
    from img2table.ocr import RapidOCR as TableOCR
ImportError: cannot import name 'RapidOCR' from 'img2table.ocr'
    (C:\Python38\Lib\site-packages\img2table\ocr\__init__.py)
```

That box runs Python 3.8 with an `img2table` predating the RapidOCR backend, so the import
raises *before* any engine-selection code can run — the Tesseract that machine actually has
was never reachable. A second, latent copy of the same bug sat on the next line
(`from rapidocr import RapidOCR`), since that package is not installed there either.

Two further details that exist because of that failure:

- **The Tesseract folder is found at runtime**, not hard-coded. `find_tesseract_dir()` walks
  up from the script looking for a `Tesseract-OCR/` directory (override with the
  `TESSERACT_DIR` environment variable). The production box runs as a different Windows user
  from a different root (`C:\Users\LaraZenl\Desktop\regulators_project\regulators_scripts\`),
  so an absolute path copied from a dev checkout silently misses and falls through to the
  wrong engine. Note `RW NBRW` still hard-codes one — this scraper deliberately does not.
- **Language is probed, not assumed.** The source is French, so `tesseract --list-langs` is
  checked for `fra` (the bundled `Tesseract-OCR/tessdata/` has `fra.traineddata`). If it is
  missing the run falls back to `eng` **and prints a warning**, because accent fidelity is a
  QA gate for this regulator — see *Language* below.
- **A failed `tesseract` call raises** instead of returning zero boxes. Zero boxes is a legal
  state ("no heading on this page"), so a crashed OCR call would otherwise push every row
  into category 0, drop the whole list, and still exit 0.

### Category 4 is excluded, by instruction

The ticket says: *"Extract all the entities of the 3 first categories, the ones under
'Institutions de microfinance de quatrième catégorie' please don't extract."* The scraper
stops the moment the category-4 heading is reached and logs
`[INFO] list 2: reached category 4 — stopping as instructed`.

Detection of all four headings was verified on the executed run — each is found exactly
once: category 1 on `image_2`, categories 2 **and 3** on `image_4`, category 4 on `image_9`.

### Category 2 is published empty — and that is real, not a miss

Categories 2 and 3 are headed on the *same* printed page: heading 2 at y = 320, heading 3 at
y = 562, and the first table on that page begins at y = 686 — **below both**. Nothing sits
between the two headings, so *Institutions de microfinance de deuxième catégorie* has no
entities in the published register. 85 = 38 (cat. 1) + 0 (cat. 2) + 47 (cat. 3).

### A wrapped legal form leaks into the address column

On 4 of the 85 rows, `Société Coopérative` wraps onto a second line inside its
*Forme juridique* cell, and `img2table` assigns that second line to the **address** column.
The raw cells read exactly `Société` / `Coopérative Province KARUSI, Commune KARUSI`.
`repair_legal_form()` puts the word back: it fires only when `CoType` is a *strict prefix* of
a known form (the column is a closed vocabulary — `Société Anonyme`, `Société Coopérative`)
and that exact missing word is present in the address, in which case the word is removed from
the address and the form completed. Without it, `COOPEC KARUSI` was landing with
`City = 'Coopérative KARUSI'`. After the fix, list 2's `CoType` holds exactly the two
legitimate values and no address begins with a stray `Coopérative`.

### List 1 entity boundaries come from the numbering, not from the markup

`node/119` is 176 flat `<p>` elements with no per-entity container. `<strong>` tagging is
inconsistent — some entries bold only the short name, some only the full name, some both,
some neither — so **markup cannot delimit entities**. The boundary is the numbered heading
line (`^\s*\d{1,2}\s*\.\s+\S`, e.g. `1. LA BANCOBU`), and the entity's official `Name` is the
line immediately after it (`BANQUE COMMERCIALE DU BURUNDI`). Category comes from the section
headers `A. BANQUE CENTRALE` / `B. LES BANQUES COMMERCIALES` / `ETABLISSEMENTS FINANCIERS`
and is stored as `License_Type`.

### French accents

All matching (labels, headings, legal forms, city names) goes through `deaccent()` — NFKD
with combining marks stripped — and uses substring or word comparison, never `==` on the raw
string. **Stored values keep their accents**: `Société Coopérative`,
`Coopérative d'Epargne et de Crédit`, `Solidarité Féminine`. Nothing is translated; `Name` is
the original French. An explicit scan of every cell in the saved workbook for `Ã`, `â€`,
`Â `, `?{3,}` and U+FFFD found **0 hits**.

Nothing from the site is ever `print()`ed — the production console is cp1252 and dies on
these accents. Every log line the script emits is ASCII (counts, page numbers, file paths).

---

## Field mapping

**List 1** (free-text labels, matched accent-insensitively after `:`):

| Source line | sqldict key | Notes |
|---|---|---|
| numbered heading + next line | `Name` | the full name, not `LA BANCOBU` |
| `A.` / `B.` / `ETABLISSEMENTS FINANCIERS` | `License_Type` | Banque Centrale / Banque Commerciale / Etablissement Financier |
| `SOCIETE MIXTE`, `SOCIETE ANONYME`, … | `CoType` | matched against a legal-form vocabulary |
| `NIF` | `InternalID_1` (+ `_type` = `NIF`) | only the central bank publishes one |
| `Code Swift` / `Swift` | `BIC SWIFT Code` | |
| `Date de création` / `Date d'obtention de Licence` / `Date d'agrément` | `RegulationDate` | first one wins |
| `Tél` / `Téléphone` | `Phone` (and `Fax` if the same line carries `fax:`) | |
| `Fax` | `Fax` | |
| `Courriel` / `Courrie` | `Email` | regex-extracted, so the typo'd label still works |
| `Site web` | `Website` | |
| `BP …` / `Avenue …` / `Boulevard …` | `Address_1` | |
| (derived from address) | `City` | see judgment call 3 |

**List 2** (columns located by header *label*, never by position — `map_columns`):

| Source column | sqldict key |
|---|---|
| `Dénomination` | `Name` |
| `Forme juridique` | `CoType` |
| `Adresse du siège` | `Address_1`, `Address_2` (the `B.P.` line), `Phone` (the `Tél:` line), `City` |
| `Date d'agrément` | `RegulationDate` |
| category heading | `License_Type` (`Institution de microfinance de première/troisième catégorie`) |

**List 3**:

| Source | sqldict key |
|---|---|
| 1st column, number stripped | `Name` |
| `A.` / `B.` / `C.` sub-heading row | `License_Type` |
| `Téléphone` | `Phone` |
| `actifs au 09 Février 2026` (page heading) | `ListValidityDate` = `2026-02-09` |

Constants on every row: `RegCtry='BI'`, `RegCode='BRB'`, `Cntry='BI'`, `ListLanguage='FR'`
(the French pages are what was parsed — the site has no English mirror of these registers),
`RegulationType='Regulated'`, `ListProcessDate = %Y-%m-%d`. `Typology` and `EntryType` are
left empty.

---

## Row-count reconciliation

The BRB prints no declared total on any of the three pages, so the authoritative count is
what the source shows. Counted by hand from the pages and the scans, then compared with the
run:

```
BI BRB 1 (Banking Supervision):     17 rows   = 1 central bank + 15 commercial banks + 1 fin. establishment
BI BRB 2 (Microfinance Supervision): 85 rows  = cat.1 38 + cat.2 0 + cat.3 47   (cat.4 excluded by instruction)
BI BRB 3 (Payment Systems):         12 rows   = 8 transfer + 3 e-money + 1 aggregator
TOTAL: 114
```

Both artefacts were executed and produced identical counts: `BI_BRB_v3.py` (17 / 85 / 12) and
`BI_BRB_v3.ipynb` executed end to end through `nbclient` with **0 error outputs**
(17 / 85 / 12). **No `drop_duplicates()` is used anywhere.**

Post-save checks on the workbook, read back with `dtype=str`:

| check | result |
|---|---|
| column names and order == frozen 43-key schema | **True**, 43 columns |
| rows per ListCode / ListLabel | `{('1','1'): 17, ('2','4'): 85, ('3','4'): 12}` |
| empty `Name` | 0 |
| encoding red flags (`Ã`, `â€`, `Â `, `?{3,}`, U+FFFD) | **0** |
| ID/Zip/Phone/Fax/SWIFT values that round-tripped as floats | **0** |
| `CoType` values in list 2 | exactly `Société Anonyme`, `Société Coopérative` |

Non-empty rates (114 rows): `Name` 100%, `CoType` 88.6%, `RegulationDate` 89.5%,
`City` 83.3%, `Address_1` 83.3%, `Phone` 52.6%, `Email` 14.9%, `Website` 10.5%,
`InternalID_1` 0.9%. The low rates are source limitations, not scrape failures — see below.

---

## What was wrong with v2

`BI_BRB_v2.ipynb` was audited before v3 was written. It cannot run today.

- **Schema violation: 44 keys, not 43.** The dict ends
  `'Phone - Mother company': [], 'Check': []}` — one illegal extra key, zero missing. This
  alone fails QA. v3 asserts `list(sqldict.keys()) == SQLDICT_KEYS` at import and routes
  every write through a single `add_row()` that raises `KeyError` on an unknown key.
- **List 3's URL is dead.** v2 points at `https://www.brb.bi/node/1551`, which returns
  **HTTP 404** (verified 2026-09-03). The ticket's `node/2928` is the live page.
- **List 2's parser is obsolete.** It reads `<p>` tags from `node/120`; that page now has
  **0 `<p>` elements and 12 `<img>`**. v2 would return 0 microfinance rows without erroring.
- **Hard-coded Windows path**:
  `scriptfolder = f"C:\Users\wuj1\OneDrive - Moody's\Desktop\Regulator\{regulatorName}"`,
  with the portable line commented out. v3 uses the `try` / `except NameError` house pattern.
- **Selenium + `webdriver_manager`.** The control server has no browser driver, and none is
  needed here. v3 is pure `requests`.

### What changed in v3

Rewritten. Pure `requests` + BeautifulSoup for lists 1 and 3; a new `img2table` + OCR
pipeline for the scanned list 2 (page splitting, second-pass table detection, line-regrouped
heading detection, label-based column mapping, wrapped-legal-form repair); the 43-key schema
enforced through `add_row()`; accent-insensitive matching with accented values preserved;
category-4 exclusion per the ticket; ID/Zip/Phone/Fax/SWIFT forced to text before `to_excel`;
the workbook re-read and asserted; and the output written to the regulator folder, not to
`tempfolder/`.

### v3.1 — OCR engine selection (2026-09-03)

The first v3 build hard-coded RapidOCR and crashed on the Windows control server with
`ImportError: cannot import name 'RapidOCR' from 'img2table.ocr'`. Replaced with
`resolve_ocr()`: Tesseract when the binary is present, RapidOCR only as a fallback, both
imports inside their branch, runtime `Tesseract-OCR/` discovery, `fra`/`eng` probing, and a
hard failure on a non-zero `tesseract` exit. See *OCR engine selection* above.
No parsing logic changed — `_ocr_lines()` was split into a shared box-regrouping step plus
one adapter per engine, so headings and tables are found exactly as before.

---

## Judgment calls for the requester

1. **List 2 `ListLabel = 4`.** Microfinance, classified as "everything else" following
   KH NBC and TJ NBTAJ. But BRB's first- and third-category MFIs **take deposits** — the
   headings read *"qui effectuent les opérations de collecte de l'épargne et d'octroi de
   crédit"*. If the convention is "labels follow deposit-taking", these 85 rows become `1`.
   **Please confirm.**
2. **`CAPITAL SOCIAL` is dropped.** Every list-1 entry publishes a share capital
   (`151 103 568 000 BIF`). The frozen 43-key schema has no field for it, so it is discarded.
   Name a target column if it should be kept.
3. **`City` is derived, not published.** Neither list 1 nor list 2 has a city column; `City`
   is matched from the free-text address against a gazetteer of Burundian provinces and
   communes. 95 of 114 rows resolved. It is *derived* — say the word and it can be blanked.
4. **The *non-actifs* payment institutions are not scraped.** `node/2928` carries a second
   table of 5 suspended / licence-withdrawn establishments with a `Statut Actuel` column
   (`Retrait d'agrément`, `En suspension volontaire d'activités`). The ticket asks for the
   register; these are negatives and would need a `RegulationType` other than `Regulated`
   (and arguably a `CancellationDate`). **Left out pending a decision — this is the one place
   a deliberate omission could be mistaken for a bug.**
5. **`Dirigeants` / `Titre` are dropped.** List 3's only other columns are the manager's name
   and title, and list 1 publishes `ADG` / `Gouverneur`. The schema has no officer field.
6. **`InternalID_1` is empty on 113 of 114 rows.** Only the central bank publishes a NIF;
   list 2 has no licence-number column and list 3's active table has none either. Source
   limitation, not a parse failure. (The *non-actifs* table does carry `N° de Permis` — a
   second reason to revisit judgment call 4.)
7. **List 3 has no address, legal form or licence date** — the active table's only columns
   are name, `Dirigeants`, `Titre`, `Téléphone`. Hence `City`/`Address_1`/`CoType`/
   `RegulationDate` are empty for all 12 rows.
8. **List 1 has no address for 7 of 17 banks** (BGF, BBCI, FINBANK, IBB, ECOBANK, KCB, BFB).
   Those entries genuinely publish no `BP` or street line.
9. **`ListValidityDate` is set only for list 3** (`2026-02-09`, from *"actifs au 09 Février
   2026"*). Lists 1 and 2 print no "as of" date.

---

## Known future breakage risks

- **List 2 is the fragile one, by a wide margin.** It depends on the BRB continuing to
  publish scans of the *same shape*: ruled table borders (`img2table` finds cells from the
  ruling lines — a borderless table returns nothing), blank bands between stacked printed
  pages, and headings worded `N. Institutions de microfinance de <ordinal> catégorie`. A
  re-scan at a different resolution, a change to the heading wording, or removal of the
  ruling lines would each break it. Failures are mostly loud (0 rows, or a `[WARN]` on a
  column-count mismatch), but a *heading* that stops matching fails **quietly and badly** —
  its entities get attributed to the previous category, and if it is the category-4 heading
  the scraper does not stop where the ticket says to stop. That exact bug produced 208 rows
  instead of 85 during development. **If a future run reports a list-2 count far above 85,
  suspect heading detection first.**
- OCR accuracy is not guaranteed row by row. Page splitting fixed the garbled rows that were
  observed, but a smudged scan can still corrupt a name silently. Names are not validated
  against any external source.
- Both HTML parsers hang off `section#block-solo-content`; a Drupal theme change breaks both
  at once, loudly (`RuntimeError`).
- List 1's parser depends on entries staying numbered (`1.`, `2.`, …) and on the official
  name being the very next line. An un-numbered entry is skipped silently.
- `BI_PLACES` is a static gazetteer; an entity in a town outside it gets an empty `City`.
- `node/1551` already went 404 once. These node IDs are not stable identifiers.

## Not verified

- **The Tesseract branch has never been executed.** `resolve_ocr()` was written against the
  control server's traceback and the `RW NBRW` pattern that is known to work there, but the
  Mac has no `tesseract` binary, so only the RapidOCR branch has actually run. What *was*
  verified on the Mac (2026-09-03): `find_tesseract_dir()` locates the bundled folder,
  `shutil.which('tesseract')` correctly declines the Windows `.exe`, the fallback is taken,
  and both `page_headings()` and `page_tables()` still work through the refactor — headings
  found on the cached pages are category 1, 2, 3 and 4, exactly as before. The Tesseract path
  — `tesseract … tsv` parsing, `--psm 3`, and the `fra` probe — is **unverified** and needs a
  control-server run. If a category heading goes missing there, `TESSERACT_PSM` is the first
  knob (try `4`), not `HEADING_RE`.
- **Any full run on the Windows control server.** Everything here was written and executed on
  the dev Mac with the project `.venv` (Python 3.13). On the RapidOCR fallback path list 2
  needs `img2table`, `rapidocr`, `opencv-python` and `onnxruntime`, and `rapidocr` downloads
  its ONNX models on first use, which a locked-down box may block — which is precisely why
  Tesseract is preferred there rather than installing that stack.
- **The v3.1 end-to-end re-run.** `www.brb.bi` was unreachable through the corporate proxy
  (`502 Bad Gateway`) when the OCR refactor was finished, so the 114-row / 17-85-12 result
  was **not** reproduced afterwards; the OCR functions were re-verified against the cached
  page images instead. The last full run is the one that produced
  `BI BRB SQL Ready 2026-09-03 12.27.53.xlsx`, from the pre-refactor code.
- Whether the BRB publishes these registers anywhere as text or PDF instead of scans. The
  site search returned 404 during development; no exhaustive hunt was done.
- Whether the 12 images on `node/120` are the complete register — there is no printed page
  count or total on the page to reconcile against. The count of 85 comes from reading the
  scans, not from a figure the BRB publishes.
- Whether an English version of any of these three pages exists.
- The share capital, `ADG`/`Gouverneur` and `Dirigeants` values are parsed past but never
  stored, so their accuracy was never checked.
