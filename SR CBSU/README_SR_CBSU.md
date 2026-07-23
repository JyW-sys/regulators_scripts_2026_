# SR CBSU

## Regulator Information

- **Country/Region Code**: SR
- **Regulator Code**: CBSU
- **Full Name**: Central Bank of Suriname (Centrale Bank van Suriname)
- **Website**: https://www.cbvs.sr/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6298

## Script

- **Current Version**: `SR_CBSU_v1.py`
- **Approach**: `requests` + `BeautifulSoup` (no browser needed) to read the
  landing page and discover one PDF link per list, then download each PDF into
  `tempfolder/` and parse it. `verify=False` for the corporate TLS proxy.
- **PDF parsing**: `pdfplumber` first; `camelot` (flavor='stream') / `tabula`
  as fallback. All four PDFs are pure scanned images (no text layer), so parsing
  actually runs through **OCR**.
- **OCR engines**:
  1. **Tesseract** (`pytesseract`) — preferred; used automatically when a working
     `tesseract` binary is found (the Windows production box, bundled
     `Tesseract-OCR/` + `tessdata/` at the repo root). Pages are rendered to
     images with the bundled **poppler** (`pdf2image.convert_from_path`,
     `poppler-25.12.0/Library/bin`), with `pypdf` `page.images` only as a
     fallback — `page.images` returns `[]` for these JPEG scans on the Py3.8
     box's older pypdf, which is what previously produced an empty output.
     `tesseract_available()` probes `get_tesseract_version()` (not just
     file-exists) so the bundled Windows `.exe`, which is present but not
     executable on the Mac, does not block the RapidOCR fallback.
  2. **RapidOCR** (`rapidocr-onnxruntime`, PP-OCR / onnxruntime) — pure-Python
     fallback that ships its own models and needs no system binary, so it runs
     on the corporate Mac where tesseract cannot be installed. The current
     output was produced with this engine. `pip install rapidocr-onnxruntime onnxruntime`.
  RapidOCR box output is re-assembled into text lines (`_rapid_page_lines`:
  group boxes by vertical centre, order left-to-right) so the item number and
  name land on one `1.  NAME` line for the parser. OCR text is NFKC-normalised
  to fold fullwidth punctuation (e.g. `，`) back to ASCII.

## List Types

The landing page (`.../suriname-financial-institutions/financial-institutions`)
has four "Click here for the &lt;ListName&gt;" paragraphs; the "here" link on each
points to one PDF (under `/images/content/publicaties/DTK_2020/`, Dutch file
names).

| ListNr | ListName | ListLabel | PDF (discovered) |
|--------|----------|-----------|------------------|
| 1 | Other Depository Corporations | 1 | Overzicht-van-ondertoezichtstaande-kredietinstellingen.pdf |
| 2 | Insurance Companies | 2 | Overzicht-van-ondertoezichtstaande-verzekeringsmaatschappijen.pdf |
| 3 | Pension- and Provident funds | 4 | Overzicht-van-ondertoezicht-staande-pensioen--en-voorzieningsfondsen.pdf |
| 4 | Money Exchange and Money Transfer Houses | 4 | Overzicht-van-ondertoezichtstaande-GTKs.pdf |

Base path: `https://www.cbvs.sr/images/content/publicaties/DTK_2020/`

**ListLabel rule** (1=bank, 2=insurance, 3=both, 4=everything else): list 1 is
depository corporations/banks → `1`; list 2 is insurance → `2`; lists 3 (pension
& provident funds) and 4 (money exchange / transfer houses) → `4`.

## PDF structure

Each list is a scanned "BEKENDMAKING" (announcement) issued by the Centrale Bank
van Suriname, **per 31 December 2019**, in **Dutch**. Layout is a numbered list
grouped under section headings, e.g. for list 1: `I. PRIMAIRE BANKEN`,
`II. SPAAR- EN KREDIETCOOPERATIES`. Each entry is:

```
1.  ENTITY NAME N.V.
    Street 1, Paramaribo
```

The scraper parses this with a numbered-line regex: the numbered line → **Name**,
the following indented line(s) → **Address_1** / **City** (token after the last
comma), with `Tel:`/`Email` pulled out by regex if present.

Parser hardening for the noisy OCR (`parse_entities`):
- **Preamble gate** — entities are only collected after the intro sentence that
  ends with `:` (`... staan ingeschreven:`). This drops the boilerplate intro,
  including list 4's `4 van de Wet ...` that would otherwise look like item 4.
- **Optional item-number dot** — RapidOCR often loses the period, emitting
  `2 STICHTING ...` instead of `2. STICHTING ...`; the number regex treats the
  `.`/`)` separator as optional so those entries are not dropped or merged.
- **Noise/stop filtering** — the repeated page footer (`Telefoon ... Telefax`),
  the closing text (`Hierin niet genoemde ...`), the signature block (`Deputy
  Governor`, official names) and the `Houdstermaatschappij` holding-company line
  are skipped, so they no longer pollute the last entity's Address/City.
- **City parenthetical** — a trailing status note in parentheses
  (`(Ingetrokken ...)`, `(respondeert niet, ...)`) is ignored when picking City;
  the note stays inside Address_1.

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | numbered entry line ("N. NAME") |
| Address_1 | address line(s) following the name |
| City | token after the last comma in the address (e.g. Paramaribo) |
| Phone / Email | regex-parsed from the address block if present |
| Cntry | `SR` |
| RegulationType | `Regulated` |
| ListName | exact ListName above |
| ListLabel | per table above (1 / 2 / 4) |
| ListLanguage | `EN` (per ticket spec; source documents are in Dutch — see QA) |
| RegCtry / RegCode / ListCode | SR / CBSU / ListNr (1–4) |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Status / QA

- **UNBLOCKED — 115 rows extracted via OCR** (previously blocked for lack of an
  OCR engine on the Mac). All four PDFs are pure scanned images (one full-page
  A4 image at ~300 DPI per page, DeviceRGB, **zero text layer**), confirmed with
  `pdfplumber` / `pypdf` (0 characters). They were OCR'd with **RapidOCR**
  (pure-Python, no system binary) and parsed with the hardened numbered-list
  parser (see PDF structure above).

  | ListNr | ListName | Rows |
  |--------|----------|------|
  | 1 | Other Depository Corporations | 38 |
  | 2 | Insurance Companies | 11 |
  | 3 | Pension- and Provident funds | 35 |
  | 4 | Money Exchange and Money Transfer Houses | 31 |
  | | **Total** | **115** |

- **Current output**: `SR CBSU SQL Ready <timestamp>.xlsx`, fixed 43-column
  schema, **0 empty names**, address & (mostly) city populated for every row.

- **This is a first-pass OCR extraction — names and City need review.** The
  counts and entity coverage are reliable, but OCR of these scans leaves noise
  that a human (or a cleaner Windows/Tesseract run) should verify:
  - **Name spacing (primary field!)**: RapidOCR occasionally drops the spaces
    inside tightly-kerned all-caps names, e.g. `SURINAAMSEPOSTSPAARBANK`,
    `KOOPERATIEVECENTRALEVANKREDIETKOOPERATIES`. The characters are right; the
    word breaks are missing. ~15–20 names (mostly the long cooperative /
    pension-fund names in lists 1 & 3) are affected.
  - **Wrapped names**: names that wrap to a second line are captured only up to
    the first line; the continuation is folded into Address_1. Also affects the
    accented spellings (`KOÖPERATIEVE`) rendered without the diaeresis.
  - **City (mostly clean)**: 94 `Paramaribo`, plus genuine districts
    (`Commewijne`, `Wanica`, `District Nickerie / Marowijne / Coronie`). The old
    date/status-note contamination is fixed by the parenthetical rule; **13 rows
    are blank** where the name wrapped and no address line was captured (see
    below), and **1 row** (list 1 `T.H.I. G.A.`) still carries a status note
    because OCR glued the next entity onto the same line.
  - **Residual OCR drops (name/number/address never read by RapidOCR)** — these
    are engine limits, not parser bugs, and a Tesseract/Windows run should
    recover most:
    - List 1: `DE DIREKTE BELASTINGEN G.A.` is glued into the `T.H.I. G.A.`
      row; three cooperative rows have wrapped names with no address.
    - List 2: entry 11's **name** is blank in the scan → its address folds into
      entry 10; 11 of 12 numbered insurers captured (holding company excluded).
    - List 3: a few rows have blank addresses; two carry an adjacent entry's
      address fragment (`21.`, `2.`) where that entry's name was unreadable.
    - List 4: `N.V. Dallex` is merged into `CYRILL'S EXCHANGE` (no number in
      OCR); `SURIFAST MONEY EXCHANGE` lost its address line.
  - **Regulatory status in the source (per-case decision needed)**: several
    entries carry Dutch status notes now preserved in Address_1 —
    `Ingetrokken d.d. 29 januari 2020` (**licence withdrawn**: list 4 EURO
    EXCHANGE, CARIBBEAN MONEYMASTERS), `in proces van ontbinding` / `gerechtelijk
    proces tot ontbinding` (**in dissolution**), `respondeert niet` (not
    responding). All rows are currently `RegulationType = Regulated`; confirm
    whether the withdrawn/dissolving ones should instead be `Cancelled` (with
    `CancellationDate`).
- **For the cleanest result, re-run on the Windows production box** (Tesseract +
  tessdata installed). The script **auto-prefers tesseract** when its binary is
  present, so no code change is needed there; Tesseract generally preserves word
  spacing better than PP-OCR on printed Latin text. Compare to the
  `LC FSRALC` / `GN BCRG` img2table+TesseractOCR pattern if table-structured OCR
  gives cleaner rows.
- **QA — also confirm**:
  - **Language**: source PDFs are Dutch; `ListLanguage` is set to `EN` per the
    ticket's English list names. Confirm whether BVD wants `NL` or a translation.
  - **Section headings as CoType**: headings such as `PRIMAIRE BANKEN`,
    `SPAAR- EN KREDIETCOOPERATIES`, `VERZEKERINGSINSTELLINGEN` are currently not
    captured into `CoType`; add if BVD wants the sub-category.
  - **Data vintage**: the published lists are dated **31 Dec 2019**; flag if a
    more recent list is required.
