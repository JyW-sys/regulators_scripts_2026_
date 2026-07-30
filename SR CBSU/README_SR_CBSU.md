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
  Both engines return **positioned OCR boxes** `(page, y, x, text)` via
  `ocr_boxes()` (row-merged within `ytol=22` px, but *not* forced onto one
  `1.  NAME` text line) — entities are then segmented by the box **geometry**
  of the item-number anchors (`parse_entities_geometric`), not by same-line
  text reconstruction; see PDF structure below. OCR text is NFKC-normalised to
  fold fullwidth punctuation (e.g. `，`) back to ASCII.

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

A single PDF holds **several independent 1..N sequences**, one per section
heading (e.g. list 1 has 5 runs: `I. PRIMAIRE BANKEN` 1-10, `II. SPAAR- EN
KREDIETCOOPERATIES` 1-19, a "niet meer operationeel" sub-list 1-4, `SPAARFONDSEN`
1, `IV. BELEGGINGS- EN FINANCIERINGSMAATSCHAPPIJEN` 1-6).

The numbered line → **Name**, the following indented line(s) → **Address_1** /
**City** (token after the last comma), with `Tel:`/`Email` pulled out by regex
if present.

**Geometric segmentation (`parse_entities_geometric`)** — entities are
segmented by the OCR box **position** of item-number anchors, not by requiring
the number and name to land on one reconstructed text line. This fixes the
main failure mode of a same-line-merge parser: when OCR places the number box
far from the name box, or drops the number entirely, the name/address used to
get silently folded into the *previous* entity. Key mechanisms:
- **Preamble gate** — entities are only collected after the intro sentence that
  ends with `:` (`... staan ingeschreven:`). This drops the boilerplate intro,
  including list 4's `4 van de Wet ...` that would otherwise look like item 4.
- **Bare-anchor recovery** — a lone number box with no name merged onto it
  (`^\d{1,3}[.)]?$`, left of `ANCHOR_X_MAX`) still opens a new entity; its name
  is filled in from the following content row(s) instead of the digit being
  discarded as noise.
- **Dropped-anchor recovery** — an ALL-CAPS row that looks like a new entity
  name (ends in a legal suffix `N.V.`/`G.A.`, or — once ruled out as a genuine
  section header by forward lookahead — any header-shaped ALL-CAPS row) starts
  a new entity even when its own number box was never OCR'd at all. The
  lookahead resolves the genuine ambiguity between "a section header" and "an
  unnumbered entity's name that merely looks header-shaped" by checking what
  comes next: a numbered anchor confirms a real header; address-shaped content
  (a comma, or non-upper text) with no number first confirms it's really a name.
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

- **UNBLOCKED — 120 rows extracted via OCR** (previously blocked for lack of an
  OCR engine on the Mac; a prior same-line-merge parser was recovering 115).
  All four PDFs are pure scanned images (one full-page A4 image at ~300 DPI per
  page, DeviceRGB, **zero text layer**), confirmed with `pdfplumber` / `pypdf`
  (0 characters). They were OCR'd with **RapidOCR** (pure-Python, no system
  binary) and segmented with the geometric parser (see PDF structure above).

  | ListNr | ListName | Entities found | Named (saved to xlsx) | Blank name |
  |--------|----------|-----------------|------------------------|------------|
  | 1 | Other Depository Corporations | 40 | 39 | 1 |
  | 2 | Insurance Companies | 12 | 11 | 1 |
  | 3 | Pension- and Provident funds | 44 | 39 | 5 |
  | 4 | Money Exchange and Money Transfer Houses | 31 | 31 | 0 |
  | | **Total** | **127** | **120** | **7** |

  Counts above are from the geometric parser run offline against the cached
  OCR box dumps (`_debug/list{1..4}_boxes.txt`) — the source `cbvs.sr` site is
  returning a `521` (origin server down, confirmed independently via two
  fetch paths) as of this update, blocking a fresh live end-to-end run. Re-run
  `SR_CBSU_v1.py` once the site is back up to confirm these counts against a
  live scrape before treating them as final.

- **Current output**: `SR CBSU SQL Ready <timestamp>.xlsx`, fixed 43-column
  schema, **0 empty names** (rows with a blank name are dropped before saving,
  same as before), address & (mostly) city populated for every saved row.

- **Fixed by the geometric rewrite** (previously lost/merged entities, now
  recovered as their own row):
  - List 1: `DE DIREKTE BELASTINGEN G.A.(SPAAR EN KREDIET KOOPERATIE A.D.B.)`
    and `SURINAAMSE TRUSTMAATSCHAPPIJ N.V.` — both had their leading item
    number dropped by OCR and were previously glued onto the prior entity.
  - List 2: entry 11 (still name-blank — OCR never produced a name at all —
    but now correctly split into its own row instead of its address folding
    into entry 10's).
  - List 3: the first `PENSIOENFONDSEN` entry (no number box at all — the
    run's very first item), plus two further dropped-anchor entries
    (`STICHTING PENSIOENFONDS ...` / Wageningen and `STICHTING
    PENSIOENFONDSS.A.A.` / BDo Assurance) and the document's last entity
    (`STICHTING VOORZIENINGSFONDS VOOR PARTICULIERE WERKNEMERS IN SURINAME`) —
    none of these three end in `N.V.`/`G.A.`, so they needed the forward-
    lookahead disambiguation (not just the tail-suffix check) to be recovered.
  - List 3: a trailing-signature leak fixed — `NOISE_RE`'s `Compliance and
    Internationa` pattern used literal spaces, but this document's OCR glued
    the phrase with none (`ComplianceandInternationalAffairs`), so it leaked
    into the last entity's Address_1. Changed to `Compliance\s*and\s*Internationa`
    to match the `\s*`-tolerant convention already used one line above for
    `CENTRALE\s*BANK\s*VAN\s*SURINAME`.

- **This is a first-pass OCR extraction — names and City still need review.**
  The counts and entity coverage are reliable, but OCR of these scans leaves
  noise that a human (or a cleaner Windows/Tesseract run) should verify:
  - **Name spacing (primary field!)**: RapidOCR occasionally drops the spaces
    inside tightly-kerned all-caps names, e.g. `SURINAAMSEPOSTSPAARBANK`,
    `KOOPERATIEVECENTRALEVANKREDIETKOOPERATIES`. The characters are right; the
    word breaks are missing. ~15–20 names (mostly the long cooperative /
    pension-fund names in lists 1 & 3) are affected.
  - **Wrapped names**: names that wrap to a second line are captured only up to
    the first line; the continuation is folded into Address_1. Also affects the
    accented spellings (`KOÖPERATIEVE`) rendered without the diaeresis.
  - **List 3, one cosmetic name artifact**: the `PENSIOENFONDSEN` sub-heading
    directly preceding the "niet meer operationeel" run's first entity is
    genuinely indistinguishable, on text shape/position alone, from that
    entry's own name (both are a short ALL-CAPS line followed eventually by an
    address with no number in between) — so the header text ends up as a
    spurious one-word prefix on that entity's name
    (`PENSIOENFONDSEN STICHTINGPENSIOENFONDS"A"...`) instead of being dropped
    cleanly. Address and entity count are unaffected; only that one name has
    the extra leading word. Judged not worth further heuristics for a single
    instance — flagging here rather than fixing silently.
  - **Remaining accepted limitations** (name/address never correctly read or
    paired by RapidOCR — engine limits, not geometric-segmentation bugs; a
    Tesseract/Windows run may recover some):
    - List 1: one entry (`KOOPERATIEVECENTRALEVANKREDIETKOOPERATIES`'s run) has
      its name and address swapped with the next entry's — an OCR box
      y-position jitter placed the address box *above* its own name box on the
      page, so the address gets attached to a blank-name entity and the name
      gets attached to the following entity's address instead. Confirmed
      pre-existing (unaffected by this round's fixes); a different root cause
      (box y-jitter, not anchor segmentation) from everything else on this list.
    - List 2: entry 11's name was never OCR'd (11 of 12 numbered insurers have
      a name; holding company excluded as before).
    - List 3: 5 entries have no name at all in the scan — bare number anchors
      (`9.`, `13.`, `21.` in the main run; `2.`, `8.` in the "niet meer
      operationeel" sub-list) directly followed by an address with no name row
      ever appearing in between.
    - List 4: `N.V. Dallex` is still merged into `CYRILL'S EXCHANGE` — its `4.`
      was never OCR'd, and unlike the other dropped-anchor recoveries above,
      `N.V.Dallex` has the legal suffix as a *prefix*, not a tail, so
      `NAME_TAIL_RE` can't catch it; it also fails the ALL-CAPS check outright
      (OCR rendered it `N.V.Dallex`, with a lowercase tail), so it never even
      reaches the header/name disambiguation. Same limitation as before.
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
