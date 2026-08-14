# SR CBSU

## Regulator Information

- **Country/Region Code**: SR
- **Regulator Code**: CBSU
- **Full Name**: Central Bank of Suriname (Centrale Bank van Suriname)
- **Website**: https://www.cbvs.sr/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6298

## Script

- **Current Version**: `SR_CBSU_v2.py` (supersedes `SR_CBSU_v1.py`)
- **Approach**: `requests` + `BeautifulSoup` to read the landing page and
  discover one PDF link per list, download each PDF into `tempfolder/`, then
  **OCR** it. `verify=False` for the corporate TLS proxy.
- All four PDFs are **pure scanned images** — `pdfplumber` / `pypdf` report
  **zero text characters**. There is no text layer to extract; OCR is mandatory,
  not a fallback. `pdfplumber` / `camelot` / `tabula` are therefore not used.

### Why v2 exists

v1 OCR'd correctly at the *character* level but reconstructed lines wrongly,
producing merged words (`SURINAAMSEPOSTSPAARBANK`,
`REPUBLIC BANK (SURINAME)N.V.`), dropped entities, and a single flat
`RegulationType = Regulated` for every row. v2 keeps the OCR engine choice and
replaces the **reconstruction and parsing** layer.

### v2 OCR pipeline (`ocr_page`)

The documents are letter-spaced monospace typewriter scans. RapidOCR's
recogniser drops intra-box spaces on that font, which is what merged the words.
v2 never asks the recogniser to read a whole line:

1. **Page image** via `pypdf` `page.images[0].data` — no poppler needed on the Mac.
2. **Pitch estimation** — measure the character pitch of the monospace font.
3. **Line segmentation by pixel ink projection** (`ink.sum(axis=1)`), not by
   detector boxes. This fixed the detector-recall gaps that lost list 3 entry 5's
   name and several item numbers. Bands closer than `0.30 × pitch` are re-merged
   so accents and quote marks re-attach to their own line.
4. **Word segmentation** by horizontal ink runs within each line band.
5. **Per-word crop re-recognition** — each word crop is fed back with
   `use_det=False, use_cls=False, use_rec=True`. Word breaks are then guaranteed
   by construction rather than inferred.
6. **Geometric column placement** — each word is placed at
   `col = round(x / pitch)`, preserving the indentation that distinguishes a
   numbered name line from its indented address lines. A word is never fused to
   its predecessor (`elif text and not text.endswith(' '): text += ' '`).
7. **Normalisation** — NFKC plus explicit fullwidth/ideographic punctuation
   mapping (`。`→`.`, `，`→`,`, `’`→`'`).

**OCR cache**: results are cached to `_debug/list{1..4}_lines.json` (~1 min/page
otherwise). Set `SR_CBSU_REOCR=1` to force a fresh OCR pass.

### v2 parsing

- **`ENTRY` is tested before `NOISE`** — deliberate. One pension fund is
  literally named `STICHTING PENSIOENFONDS VAN DE CENTRALE BANK VAN SURINAME`;
  a letterhead substring filter applied first deleted it (real data loss in v1).
- **`TITLE` is anchored and matched loosely** (`^\W*B\s*E\s*K\s*E\s*N\s*D...`).
  It must NOT be a loose `BEKEND` search — that also matches the ordinary word
  *"bekend,"* in the preamble sentence, which is the line carrying the
  `ListValidityDate`. That bug left `ListValidityDate` empty on all rows in v1.
  The date is now extracted **before** any filtering.
- **`ROMAN_SECTION` + `looks_like_section()`** run regardless of whether an entry
  is open, flushing the current entry. In v1 section detection only ran when no
  entry was open, so all 40 list-1 rows inherited the first heading
  (`PRIMAIRE BANKEN`).
- **`SIGNOFF`** regex + an `in_signature` skip flag stop the signature block
  (`Paramaribo, 29 januari 2020`, `F. Hausil`, `Deputy Governor …`) leaking into
  `Address_2`. The flag resets when a genuine numbered entry appears.
- **`is_address()`** discriminates a wrapped company-name line from a real
  address line. An address is either an explicit `p/a` (c/o) line, a line naming
  one of the ten districts, or a mixed-case line carrying a house number.
  Wrapped name lines are ALL CAPS (`BEDRIJVEN N.V.`) or start with a legal form
  (`G.A., …`, `C-47 G.A. (C-47 Coop)`), so they fail all three tests.
- **`finish_entry()`** does a look-ahead split: everything before the first
  `is_address()` line is name continuation, everything after is address.

## List Types

The landing page (`.../suriname-financial-institutions/financial-institutions`)
has four "Click here for the &lt;ListName&gt;" paragraphs. All four anchors'
visible text is just the word **"here"**, so link discovery matches on the href
instead: `'dtk_2020' in href.lower() and meta['slug'] in href.lower()`.

| ListNr | ListName | ListLabel | slug |
|--------|----------|-----------|------|
| 1 | Other Depository Corporations | 1 | `kredietinstellingen` |
| 2 | Insurance Companies | 2 | `verzekeringsmaatschappijen` |
| 3 | Pension- and Provident funds | 4 | `pensioen` |
| 4 | Money Exchange and Money Transfer Houses | 4 | `gtks` |

Base path: `https://www.cbvs.sr/images/content/publicaties/DTK_2020/`

**ListLabel rule** (1=bank, 2=insurance, 3=both, 4=everything else): list 1 is
depository corporations/banks → `1`; list 2 is insurance → `2`; lists 3 (pension
& provident funds) and 4 (money exchange / transfer houses) → `4`.

## PDF structure

Each list is a scanned "BEKENDMAKING" (announcement) issued by the Centrale Bank
van Suriname, **per 31 December 2019**, in **Dutch**. Layout is a numbered list
grouped under section headings. A single PDF holds **several independent 1..N
sequences**, one per section heading:

```
I.  PRIMAIRE BANKEN
1.  ENTITY NAME N.V.
    Street 1, Paramaribo
```

10 sections across the 4 PDFs. Some carry status information in the heading
itself (`... DIE NIET MEER OPERATIONEEL ZIJN:`), some inline per entry
(`(Ingetrokken d.d. 29 januari 2020)`, `in proces van ontbinding`).

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | numbered entry line + any wrapped continuation lines |
| Address_1 | address line(s) after the name/address split |
| City | district token from the district-bearing address line (addresses wrap; the district is usually last) |
| CoType | the section heading the entry falls under |
| Phone / Email | regex-parsed from the address block if present |
| Cntry | `SR` |
| RegulationType | see branching below |
| CancellationDate | the `Ingetrokken d.d. …` date, when present |
| ListValidityDate | `2019-12-31` (parsed from the preamble sentence) |
| ListName | exact ListName above |
| ListLabel | per table above (1 / 2 / 4) |
| ListLanguage | `NL` — **changed from v1's `EN`**; the source documents are Dutch |
| RegCtry / RegCode / ListCode | SR / CBSU / ListNr (1–4) |
| ListProcessDate | run date (`%Y-%m-%d`) |

### RegulationType branching (v2)

```python
if e['cancel']:                                              # "(Ingetrokken d.d. ...)"
    RegulationType = 'Withdrawn';      CancellationDate = e['cancel']
elif re.search(r'NIET\s+MEER\s+OPERATIONEEL', e['section'], re.I):
    RegulationType = 'Not Operational'
elif e['status']:                                            # "in proces van ontbinding"
    RegulationType = 'In Liquidation'
else:
    RegulationType = 'Regulated'
```

## Status / QA

- **Current output**: `SR CBSU SQL Ready 2026-08-05 16.58.29.xlsx`, fixed
  43-column schema.
- **130 rows / 130 distinct names** (v1: 120).

  | ListNr | ListName | v1 rows | v2 rows |
  |--------|----------|---------|---------|
  | 1 | Other Depository Corporations | 39 | 40 |
  | 2 | Insurance Companies | 11 | 13 |
  | 3 | Pension- and Provident funds | 39 | 45 |
  | 4 | Money Exchange and Money Transfer Houses | 31 | 32 |
  | | **Total** | **120** | **130** |

- **Completeness**: `Name`, `Address_1`, `City`, `CoType`, `ListValidityDate` are
  **130/130 non-empty**. `ListValidityDate` = `2019-12-31` on every row.
- **Numbering integrity**: **zero gaps** in the per-section entry numbering across
  all 10 sections — i.e. every `1..N` run is complete, which is the strongest
  available check that no entity was dropped.
- **RegulationType distribution**: Regulated 117, In Liquidation 7,
  Not Operational 4, Withdrawn 2. (v1 emitted only `Regulated`.)
- **Sections recovered that v1 collapsed into the preceding heading**:
  `SPAAR- EN KREDIETCOOPERATIES DIE NIET MEER OPERATIONEEL ZIJN:` (4 entries),
  `GELDOVERMAKINGSKANTOREN` (7), `SPAARFONDSEN` (1),
  `BELEGGINGS- EN FINANCIERINGSMAATSCHAPPIJEN` (6), `VOORZIENINGSFONDSEN` (5).
- **Spot-checks passed**: the CENTRALE BANK pension fund (the entity v1 deleted
  as letterhead noise), KOOPERATIEVE CENTRALE, C-47, S.A.A. (In Liquidation),
  UNIFOREX.
- **Word-merge defects from v1 are gone** — `SURINAAMSE POSTSPAARBANK`,
  `SURINAAMSE VOLKSCREDIETBANK` etc. now carry correct word breaks.

### Known remaining artifact

- One cosmetic OCR misread: `G.A. 1 (de A.V.K.C.)` — the source reads `G.A.,`
  and OCR rendered the comma as `1`. Single instance, name otherwise correct.

### Items needing your confirmation

1. **`ListLanguage` changed `EN` → `NL`.** The source documents are Dutch; only
   the ticket's list *titles* are English. Revert if BVD expects `EN`.
2. **New `RegulationType` values** — `Withdrawn`, `Not Operational`,
   `In Liquidation`. CLAUDE.md says non-`Regulated` cases are decided case by
   case, so confirm these three strings are the ones BVD wants (and that
   `Withdrawn` is preferred over `Cancelled`).
3. **Data vintage**: the published lists are dated **31 Dec 2019**. Flag if a
   more recent list is required — the regulator has not republished since.
4. **`CoType` now carries the section heading** (`PRIMAIRE BANKEN`,
   `SPAAR- EN KREDIETCOOPERATIES`, `VERZEKERINGSINSTELLINGEN`, …). v1 left it
   empty. Confirm this is the wanted sub-category field.

### Environment notes

- OCR uses **`rapidocr-onnxruntime`** (pure Python, ships its own models, no
  system binary) — required because tesseract cannot be installed on the
  corporate Mac. `pip install rapidocr-onnxruntime onnxruntime`.
- Page images come from `pypdf` `page.images`, avoiding a poppler dependency.
  On the **Windows production box**, poppler and Tesseract are both available;
  a Tesseract run may be worth comparing, but v2's per-word crop recognition has
  already removed the word-spacing defect that motivated preferring Tesseract.
