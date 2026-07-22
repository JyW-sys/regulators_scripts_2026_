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
- **OCR engines** (`pypdf` extracts each page image — no poppler needed):
  1. **Tesseract** (`pytesseract`) — preferred; used automatically when a
     `tesseract` binary is found (the Windows production box).
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

- **UNBLOCKED — 106 rows extracted via OCR** (previously blocked for lack of an
  OCR engine on the Mac). All four PDFs are pure scanned images (one full-page
  A4 image at ~300 DPI per page, DeviceRGB, **zero text layer**), confirmed with
  `pdfplumber` / `pypdf` (0 characters). They were OCR'd with **RapidOCR**
  (pure-Python, no system binary) and parsed with the numbered-list parser.

  | ListNr | ListName | Rows |
  |--------|----------|------|
  | 1 | Other Depository Corporations | 37 |
  | 2 | Insurance Companies | 11 |
  | 3 | Pension- and Provident funds | 33 |
  | 4 | Money Exchange and Money Transfer Houses | 25 |
  | | **Total** | **106** |

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
  - **City noise (~13 rows)**: most are correct (`Paramaribo`, or genuine
    districts `District Wanica / Nickerie / Marowijne / Coronie`), but a few
    grabbed stray line content instead of a locality (a date `29 januari 2020`,
    a note `(post geretourneerd als onbestelbaar)`) or are blank where the name
    wrapped. City is a secondary field here; the full locality is inside Address_1.
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
