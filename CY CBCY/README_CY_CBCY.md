# CY CBCY — Central Bank of Cyprus

Jira: [DECD-5538](https://moodysdatapipeline.atlassian.net/browse/DECD-5538) (parent epic DECD-3438) · Language: English · All entities `RegulationType = Regulated`.

## Source

Four registers published on `https://www.centralbank.cy`. The site **403s plain bots**, so the
scraper sends a desktop-Chrome `User-Agent` + `Referer` header. Data comes from a mix of an HTML
landing page, two enrichment **PDFs**, and three **Excel** workbooks (`requests` downloads each into
`tempfolder/`; no Selenium / OCR needed).

| ListCode | ListName | Source | Extraction |
|---|---|---|---|
| 1 | Register of Credit Institutions operating in Cyprus | HTML landing page + 2 PDFs | names + category from the page; **National Identification Code** and **LEI Code** joined in from the two PDFs |
| 2 | Register of Payment Institutions | `PI-register-*.xlsx`, sheet **`PI licensed in CY`** | one row per licensed PI |
| 3 | Register of Electronic Money Institutions licensed by the CBC | `EMI-REGISTER-*.xlsx`, sheet **`EMIs`** | one row per licensed EMI |
| 4 | Register of EMIs from other EU member states notified to provide services in Cyprus | `emi-incom-passp-register-*.xlsx`, sheet **`EMIs passp to Cyprus`** | one row per passporting (incoming) EMI |

> The CBC rotates the date suffix on every file (`PI-register-17062026.xlsx`, etc.). The scraper
> hard-codes the links verified **2026-06-18**; on a stale-link 404, re-scrape the landing page for
> the current href (the link *text* is stable).

## Extraction notes

- **List 1 — name → code join.** The landing page lists 16 institutions under category headings
  (`1. LOCAL AUTHORISED…`, `A./B. SUBSIDIARIES/BRANCHES OF FOREIGN…`, `3. REPRESENTATIVE OFFICES`);
  the heading is stored in `CoType` / `License_Type`. The two PDFs (`National-ident-code-list`,
  `BANKS-LEI-CODES`) are matched back by a normalised name key — `norm_name()` unifies `Ltd`/
  `Limited`, drops `(The)` and `(previous name: …)` notes, folds the Greek capital `Α` to Latin
  `A` (e.g. *Αlpha Bank*), and strips the `*` footnote. Result: **16/16** National IDs and **8/8**
  available LEIs (the LEI PDF only covers institutions *incorporated in* Cyprus, so foreign
  branches / the representative office have none — expected).
- **Lists 2 & 3 — interleaved spacer rows.** The Excel sheets put a blank row between every entity;
  the parser skips rows with an empty Name. `InternalID_1` = HE registration number, `InternalID_2`
  = CBC licence number, plus `LEI Code`. The `Contact details` cell (`H.O. address: <street>, <ZIP>
  <City>`) is split into `Address_1` / `Zip` / `City`, `Cntry = CY`. Auth/licence dates (text
  `Current Lic. Date: dd/mm/yyyy` *or* a bare datetime cell) → `RegulationDate`.
- **List 4 — incoming passporting.** 234 foreign EMIs. `Cntry` = the institution's **home country**
  (2-letter code from the sheet); `RegCtry` stays `CY` (notified to Cyprus). Greek-homoglyph codes
  are normalised (`ΙΕ` → `IE`). No address/ID columns are published for these.
  - **Known source quirk:** one row (`iLedgends B.V.`) carries home country `NV` in the source —
    almost certainly a typo for `NL`. Left **verbatim** rather than guessed; flag at validation.

## Output

`CY_CBCY_v1.py` → `tempfolder/CY CBCY SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`).
Total: **289 entities** — List 1: 16 · List 2: 10 · List 3: 29 · List 4: 234.
