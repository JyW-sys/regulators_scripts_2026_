# GY BGU — Bank of Guyana

Jira: [DECD-5024](https://moodysdatapipeline.atlassian.net/browse/DECD-5024) (parent epic DECD-3438)

## Source

Five **text-based PDF** registers published on `https://www.bankofguyana.org.gy`
(no scanning / OCR needed). The scraper downloads each PDF with `requests` and parses it
by **table grid**:

- **Lists 2 / 3 / 4** — `pdfplumber.extract_tables()`, driven by a per-list `CONF` that maps the
  Name / Address / Date columns by header keyword.
- **Lists 1 / 5** *(v2)* — `camelot` (`flavor='lattice'`), which reads the PDF's ruled cell
  borders. This is more reliable than `pdfplumber` for these two registers (see notes below).

## Lists (ListCode = Jira ListNr)

| ListCode | ListName | Name column | Engine | Notes |
|---|---|---|---|---|
| 1 | Commercial Banks | `Commercial Banks` | camelot | first address line only (HQ) per Jira; branch rows skipped |
| 2 | Non-Bank Financial Institutions | `INSTITUTION` | pdfplumber | name = first line (drops the `(business-type)` note) |
| 3 | Registered Insurance Companies in Guyana | `INSURANCE COMPANY` | pdfplumber | address = first line of `REGISTERED ADDRESS` |
| 4 | Registered Insurance Brokers in Guyana | `Names of Insurance Brokers` | pdfplumber | + `Initial Date of Registration` → `RegulationDate`; includes the **Special Brokers** section |
| 5 | Pension Plan Managers | `NAMES OF PLAN MANAGERS` | camelot | entity = the **plan manager** (not the plan) per Jira |

### Handling notes

- **List 1 — camelot (v2):** `pdfplumber.extract_tables()` silently dropped bank **#6 "Bank of
  Baroda (Guyana) Incorporated"**, which sits at the bottom of the final page with no inline
  address row. Camelot reads the ruled grid and recovers all **6** banks directly, replacing v1's
  `extract_text()` regex page-break-recovery workaround. A small `fix_split_lead()` re-joins the
  leading glyph camelot occasionally splits off a name (e.g. `R epublic` → `Republic`).
- **List 5 — camelot, one row per plan (v2):** the PDF is a two-column table
  (`NAMES OF PENSION PLANS | NAMES OF PLAN MANAGERS`) over two sections — 16 Defined Benefit + 43
  Defined Contribution = **59 plans**. v2 emits one row per plan with `Name` = that plan's manager,
  **including** the generic `Plan's Trustees` value (v1 excluded it). After the global de-dupe
  (below) this collapses to **8 distinct managers**.
- **Global de-dupe (v2):** `df.drop_duplicates(subset=['Name','ListCode'], keep='first')` runs once
  before output, deduping every list by name. Effect: List 4 drops the 3 firms (Abdool & Abdool,
  MP, P&P) that appear in both the *Registered Brokers* and *Special Brokers* sections → **12 rows**
  (the second registration's date is lost, `keep='first'`); List 5 → **8**. ⚠️ This reverses v1's
  treatment of List 4's cross-section entries as separate registrations.
- **Punctuation:** the PDFs use Unicode smart quotes/dashes (U+2019, U+2013 — valid, not mojibake);
  `clean()` normalizes them to ASCII. The undecodable glyph `�` is mapped to `'`.

## Output

`tempfolder/GY BGU SQL Ready <timestamp>.xlsx`, sheet **"SQL Ready"**, standard `sqldict` schema.

- `RegCtry`=GY, `RegCode`=BGU, `Cntry`=GY.
- `RegulationType`=**Regulated** (all on licensed/registered lists).
- `RegulationDate` populated for List 4 (broker initial registration date, `yy/mm/dd`).
- `ListProcessDate`=run date.

**Name-list PDFs (v2):** one paginated PDF per `(RegCtry, ListCode)` is written next to the xlsx via
`reportlab` (`export_list_to_pdf`, Arial → Helvetica fallback), e.g.
`GY BGU SQL Ready <timestamp> - GY-1.pdf`. End-of-run cleanup removes only the downloaded source
PDFs (`GY_BGU_<n>.pdf`), keeping the xlsx and these list PDFs.

## Run

```
python "GY BGU/GY BGU_v2.py"
```

Needs `camelot-py` and `reportlab` (in addition to `pdfplumber`/`pandas`). v1 (`GY BGU_v1.py`,
pdfplumber-only, no PDF output) is kept as the prior version.

## Last run (2026-06-12, v2) — 51 entities

| ListCode | ListName | rows |
|---|---|---|
| 1 | Commercial Banks | 6 |
| 2 | Non-Bank Financial Institutions | 7 |
| 3 | Registered Insurance Companies | 18 |
| 4 | Registered Insurance Brokers (incl. Special Brokers) | 12 |
| 5 | Pension Plan Managers | 8 |

Counts verified against each PDF's own numbering. Name 100%, 0 non-ASCII residue.
