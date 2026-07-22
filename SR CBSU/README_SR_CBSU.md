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
  as fallback. An OCR fallback (`pypdf` image extraction + `pytesseract`) is
  included but only fires when a `tesseract` binary is present.

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

- **BLOCKED — needs OCR on the Windows box.** All four PDFs are pure scanned
  images (one full-page A4 image at ~300 DPI per page, DeviceRGB, **zero text
  layer**). `pdfplumber`, `camelot` and `tabula` all rely on a text layer and
  return nothing; `camelot` itself reports each page as "image-based". On this
  Mac the `tesseract` binary is not installed and the only bundled `poppler` is
  a Windows `.exe`, so OCR cannot run here. Per project rules the scraper marks
  each list BLOCKED and does **not** fabricate rows.
- **Current output**: `SR CBSU SQL Ready <timestamp>.xlsx` with the fixed
  43-column schema and **0 data rows** (all lists blocked).
- **To complete**: run `SR_CBSU_v1.py` on the Windows production box (Tesseract
  installed). The included OCR fallback auto-activates when `tesseract` is found;
  it extracts the embedded page image with `pypdf` (no poppler needed) and OCRs
  it with `pytesseract`, feeding the same numbered-list parser. Compare to the
  `LC FSRALC` / `GN BCRG` img2table+TesseractOCR pattern if a table-structured
  OCR gives cleaner results.
- **QA — verify after OCR**:
  - **Language**: source PDFs are Dutch; `ListLanguage` is set to `EN` per the
    ticket's English list names. Confirm whether BVD wants `NL` or a translation.
  - **Wrapped names**: a name that wraps to a second line (e.g. list 1
    "KOÖPERATIEVE CENTRALE VAN KREDIET KOÖPERATIES G.A., (de A.V.K.C.) …") is
    parsed with the continuation folded into Address_1. Review multi-line names.
  - **Section headings as CoType**: headings such as `PRIMAIRE BANKEN`,
    `SPAAR- EN KREDIETCOOPERATIES`, `VERZEKERINGSINSTELLINGEN` are currently not
    captured into `CoType`; add if BVD wants the sub-category.
  - **Data vintage**: the published lists are dated **31 Dec 2019**; flag if a
    more recent list is required.
