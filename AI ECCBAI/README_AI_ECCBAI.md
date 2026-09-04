# AI ECCBAI — Eastern Caribbean Central Bank

**Jira:** DECD-6832 — AI ECCBAI
**Regulator:** Eastern Caribbean Central Bank (ECCB)
**ListLanguage:** `EN`
**Run:** `python3 AI_ECCBAI_v2.py` (or open `AI_ECCBAI_v2.ipynb`)

The ECCB is **one supranational central bank shared by eight Eastern Caribbean member
territories**. The ticket is filed under Anguilla (`AI`), but its comment says *"collect all
entities and addresses from the different countries"*, so **all eight territories are scraped**.

Because the licence is issued by the currency union rather than by a national regulator, the
register is parsed **once** and then emitted **once per member regulator** — the same treatment
`CF CEMACCF` gives the six CEMAC/COBAC members. See *Multi-regulator output* below.

| Territory (`RegCtry` / `Cntry`) | `RegCode` |
|---|---|
| `AI` Anguilla | `ECCBAI` |
| `AG` Antigua and Barbuda | `ECCBAG` |
| `DM` Commonwealth of Dominica | `ECCBDM` |
| `GD` Grenada | `ECCBGD` |
| `KN` Saint Christopher (St Kitts) and Nevis | `ECCBKN` |
| `LC` Saint Lucia | `ECCBLC` |
| `MS` Montserrat | `ECCBMS` |
| `VC` Saint Vincent and the Grenadines | `ECCBVC` |

---

## Version history

| Version | Change |
|---|---|
| `v1` | Initial build. 31 rows, one workbook, all tagged `RegCtry`/`RegCode` = `AI`/`ECCBAI`. |
| `v2` | **Multi-regulator.** Same 31 parsed rows replicated across all eight ECCB member regulators → 248 rows, written as **eight workbooks, one per regulator**, sharing one run timestamp. Parsing logic unchanged. |

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Unique rows | Delivered rows |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | Licensed Finance Companies | https://www.eccb-centralbank.org/register-of-licensed-financial-institutions | PDF (`pdfplumber`, ruled table) | **31** | **248** (31 × 8 regulators) |

**ListLabel = 1 (bank).** The register is issued under **section 13(1) of the Banking Act, 2015**
and contains commercial banks, non-bank credit institutions and bank holding companies. It is a
banking-sector register with no insurance content, so `1` rather than `3` or `4`.

**ListValidityDate = `2026-06-25`**, parsed from the anchor label (`… Banking Act 25.6.26`) with
the upload-date stamp in the href as fallback.

---

## Multi-regulator output (v2)

The PDF is downloaded and parsed **once**. The resulting 31-row frame is tagged
`RegCtry`/`RegCode` = `AI`/`ECCBAI`, then copied seven more times with `RegCtry`/`RegCode`
rewritten to each of the other member territories. **`Cntry` is never rewritten** — it keeps
carrying the territory the institution is actually licensed in, so *every* regulator copy holds
the full eight-territory list:

```
Rows per RegCtry / RegCode        Rows per Cntry, within any one copy
  AG  ECCBAG   31                   AG 6   AI 2   DM 2   GD 3
  AI  ECCBAI   31                   KN 5   LC 8   MS 1   VC 4
  DM  ECCBDM   31                   ------------------------------
  GD  ECCBGD   31                   total 31
  KN  ECCBKN   31
  LC  ECCBLC   31
  MS  ECCBMS   31
  VC  ECCBVC   31
  ----------------
  total       248
```

**Why the full list per regulator, not just each regulator's own territory?** Because that is
the shape `CF CEMACCF_v2` ships (61 unique rows × 6 CEMAC regulators = 366 rows, each carrying
all six `Cntry` values). The country-filtered alternative is present in that scraper but
commented out. To switch to it here, set **`OWN_COUNTRY_ONLY = True`** in the *Variable* section
— that yields 31 rows total (each regulator getting only its own territory's licensees).

Two guards run at import time and will fail loudly rather than ship a lopsided file:

- the eight regulator ISO codes must equal the set of ISO codes the PDF-section parser can
  produce (`COUNTRY_TOKEN_TO_ISO`) — so an ECCB membership change breaks the run;
- every `RegCode` must equal `'ECCB' + RegCtry`.

Post-replication the script asserts `248 == 31 × 8` and that eight distinct `RegCode`s are
present.

### One workbook per regulator

`WRITE_PER_REGULATOR = True` (default) splits the frame on `RegCode` and writes **eight
files into this folder**, all carrying the *same* run timestamp so they read as one delivery:

```
AG ECCBAG SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
AI ECCBAI SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
DM ECCBDM SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
GD ECCBGD SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
KN ECCBKN SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
LC ECCBLC SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
MS ECCBMS SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
VC ECCBVC SQL Ready 2026-08-25 14.50.21.xlsx     31 rows
                                          total 248 rows
```

Naming follows the repo convention `<RegCtry> <RegCode> SQL Ready <stamp>.xlsx`, so each file
is named for the regulator it belongs to rather than for this folder.

Every workbook is **written, re-read and asserted individually** (row count, 43-column schema,
no scientific-notation coercion, `Name` present and re-read as a string). A final check re-opens
all eight and asserts they sum back to the 248 in-memory rows.

`WRITE_COMBINED = True` *additionally* writes all 248 rows into one workbook named
`AI ECCBAI ALL SQL Ready <stamp>.xlsx` — the `ALL` infix exists so it cannot be mistaken for,
or overwrite, the 31-row Anguilla workbook. Off by default; the eight files already hold the
same data.

Both flags live in the *Variable* section.

---

## Site quirks (these will break a naive scraper)

1. **The PDF URL in the Jira ticket is already stale.** The ticket points at
   `2024-07-30-13-55-38-Register-of-Financial-Institutions-Licensed-Under-the-Banking-Act.pdf`.
   The index page now links a newer revision,
   `2026-06-25-16-12-51-…-Banking-Act-25.6.26.pdf`. The ticket's old URL still returns HTTP 200
   with `%PDF` magic bytes, but the payload is **truncated/corrupt** — `pdfplumber` fails on it
   with `No /Root object! - Is this really a PDF?`. Building against the ticket URL would have
   produced either a crash or stale 2024 data.
   → The scraper resolves the link **every run by the anchor's visible label**
   (`ANCHOR_KEYWORD = 'register of financial institutions licensed under the banking act'`) and
   raises a loud `SKIPPED - no anchor whose label contains …` if the label ever disappears.

2. **Column count varies between pages** — pages 1–5 render 9 columns, pages 6–11 render 10.
   Column indices are therefore mapped **per page from that page's own header row**, never
   positionally.

3. **The header wording changes mid-document** — pages 1–5 print `BRANCH LOCATION2`, pages 6–11
   print `BRANCH LOCATION**S**2`. A first implementation that recognised the repeated header by
   comparing it byte-for-byte against page 1 silently dropped pages 6–11 (19 rows instead of 31).
   Header recognition is now pattern-based (`HEADER_CELL_PATTERNS`).

4. **The header is stacked over four physical rows** (`NAME OF LICENSED` / `FINANCIAL` /
   `INSTITUTION OR` / `HOLDING COMPANY`), so per-column header text is rebuilt by concatenating
   all header rows before matching.

5. **The licensee name sits in merged cells that do not align with its own header column.** The
   header `NAME OF LICENSED …` lands at column index 2 while the data lands at index 1. The name
   is therefore read as the **join of every column between `NO` and `HEAD OFFICE`**.

6. **Country section headings do not match the ticket's wording.** The ticket says
   `ST KITTS AND NEVIS`; the PDF prints `SAINT CHRISTOPHER (ST KITTS) AND NEVIS`. Headings are
   detected **structurally** (exactly one non-empty cell, all-caps, no digits) rather than from a
   hard-coded list, then normalised to ISO-2 by token match. An unrecognised heading raises loudly
   instead of silently mis-assigning a country.

7. **Tall rows split across page breaks.** e.g. *Bank of St Vincent and the Grenadines Limited*
   begins on page 9 (name present, `NO` blank) and continues on page 10 (`NO`=1, name blank).
   Rule: a row with a non-empty name starts a new licensee; a row with a blank name is appended
   to the previous one.

8. **Parent company name is embedded in the address column.** Where a licensee is a subsidiary,
   the first line of `HEAD OFFICE/PARENT COMPANY'S ADDRESS` is the *parent's name*, not an address
   (`Republic Financial Holdings Limited` / `Fourth Floor, Republic House` / …). `Not applicable`
   means no foreign parent.

9. **PDF word-wrap corrupts tokens** — `Co- operative` for `Co-operative`, `Limit ed`. Repaired by
   `flatten()`.

10. Site is plain `requests` + BeautifulSoup — **no JS rendering, no bot defence, no DrissionPage
    needed**. Corporate TLS proxy requires `verify=False`.

---

## Field mapping (List 1)

| PDF column | sqldict field | Notes |
|---|---|---|
| NAME OF LICENSED FINANCIAL INSTITUTION OR HOLDING COMPANY | `Name` | joined across the merged name block |
| MAILING ADDRESS OF PRINCIPAL OFFICE IN CURRENCY UNION | `Address_1` | flattened to one line |
| — derived from `Address_1` | `City` | heuristic, see below |
| BRANCH LOCATION(S) | `Address_2` | `None` / `Not applicable` → empty |
| CLASS OR CATEGORY OF LICENCE HELD | `License_Type` | e.g. `Local LFI (Bank)`, `CARICOM incorporated Bank treated as local LFI` |
| RESTRICTIONS LISTED ON LICENCE | `CoType` | `None` → empty |
| HEAD OFFICE/PARENT COMPANY'S ADDRESS (line 1) | `Name - Mother Company` | blank when `Not applicable` |
| HEAD OFFICE/PARENT COMPANY'S ADDRESS (rest) | `Address_1 - Mother company` | |
| country section heading | `Cntry` | ISO-2 of the **licensing** territory — unchanged by the replication |
| — | `RegulationType` | `Regulated` (positive register) |
| — | `RegCtry` / `RegCode` | one of the eight pairs in the table at the top; every row is emitted under all eight |
| — | `ListLanguage` | `EN` |
| — | `ListCode` / `ListLabel` / `ListName` | `1` / `1` / `Licensed Finance Companies` |
| — | `ListValidityDate` / `ListProcessDate` | `2026-06-25` / run date |

The `NO` column is a **per-country sequence number, not an institution identifier**, so it is
used only for reconciliation and is *not* written to `InternalID_1`.

**City heuristic.** The register writes addresses as `[PO Box] / [street] / [town] / [territory]`,
so `City` is taken as the line above the territory, with trailing territory lines stripped
(the territory itself may wrap, e.g. `Saint Vincent and the` + `Grenadines`). This resolves
correctly for 29 of 31 rows. Two rows still capture a street fragment —
*Finance & Development Company Limited* (`Road, St John's, Antigua and`) and
*Capita Financial Services Inc* (`Centre, Gros Islet`) — because those addresses wrap
mid-street-name. Flagged below for the requester.

---

## Row-count reconciliation

The register numbers its entries **per country** in the `NO` column. The scraper parses that
number and compares it with the rows it produced. Reconciliation runs on the **31 unique parsed
rows, before replication** — the ×8 that follows is a pure copy. Output of the actual run
(2026-08-25):

| Country section (as printed in the PDF) | Cntry | Scraped | Declared max `NO` | |
|---|---|---|---|---|
| ANGUILLA | AI | 2 | 2 | OK |
| ANTIGUA AND BARBUDA | AG | 6 | 6 | OK |
| COMMONWEALTH OF DOMINICA | DM | 2 | 2 | OK |
| GRENADA | GD | 3 | 3 | OK |
| MONTSERRAT | MS | 1 | 1 | OK |
| SAINT CHRISTOPHER (ST KITTS) AND NEVIS | KN | 5 | 5 | OK |
| SAINT LUCIA | LC | 8 | 8 | OK |
| SAINT VINCENT AND THE GRENADINES | VC | 4 | 4 | OK |
| **Total** | | **31** | **31** | **all sections reconcile** |

Any mismatch prints `*** MISMATCH ***` and a `WARNING` line in the run log.

**Deliberate duplicates — do not dedupe.** Several institutions are licensed in more than one
territory and are therefore listed once per territory by the source:
`Republic Bank (EC) Limited` ×4 (DM, KN, LC, VC), `CIBC Caribbean Bank (Barbados) Limited` ×3
(AG, KN, LC), `1st National Bank St Lucia Limited` ×2 (LC, VC). Row count matches the source's
own count; removing them would break QA-by-row-count.

---

## Judgment calls for the requester

1. **Scope — all eight territories, not just Anguilla.** The ticket is filed as `AI` but its
   comment asks for "all entities and addresses from the different countries". Delivered all 31
   rows across 8 territories with `Cntry` varying. **If only Anguilla is wanted, the answer is
   2 rows.** Please confirm.
1b. **Replication shape (v2).** Each of the eight `ECCB<CC>` regulator codes receives the full
   31-row register (248 rows total), following `CF CEMACCF`. If the intent is instead "each
   regulator owns only its own territory", set `OWN_COUNTRY_ONLY = True` → 31 rows total,
   spread over the eight files as 2/6/2/3/5/8/1/4. Confirm which shape is wanted.
1c. ~~Should the eight workbooks go into sibling `AG ECCBAG/`, `KN ECCBKN/`, … folders?~~
   **Settled (2026-08-25): no.** All eight stay in `AI ECCBAI/`. No new regulator folders are
   created for the other seven ECCB members — this scraper owns the whole currency union.
2. **ListName mismatch.** The ticket calls List 1 *"Licensed Finance Companies"*; the source
   document is titled *"Register of Financial Institutions and Financial Holding Companies
   Licensed Under the Banking Act, 2015"*. The ticket's `ListName` was used verbatim. Confirm
   whether it should be renamed to match the source.
3. **A second register exists and was NOT scraped.** The same index page also links
   *"Register of Financial Institutions with Revoked Licences"*
   (`…2024-07-30-13-56-30-Register-of-Financial-Institutions-with-Revoked-Licences.pdf`). The
   ticket does not mention it. If wanted, it would be List 2 with
   `RegulationType = 'Deregistered'`/`CancellationDate` rather than `Regulated`.
4. **`Cntry` for cross-border listings.** For an institution licensed in territory X whose
   principal office address is in territory Y (e.g. `Republic Bank (EC) Limited` listed under
   St Vincent but with a Castries, Saint Lucia mailing address), `Cntry` is set to the
   **licensing territory** (VC), not the address territory (LC). Confirm this is the wanted
   convention.
5. **Branch locations in `Address_2`.** Branch addresses are a list of separate premises, not a
   second address line. They are flattened into `Address_2` to avoid discarding data. Confirm, or
   say if they should be dropped / split into their own rows.
6. **Two imperfect `City` values** (see City heuristic above) — happy to hard-correct those two if
   preferred over a purely derived value.
7. **Contact details are not in this register.** `Phone`, `Fax`, `Email`, `Website` are all empty.
   The ECCB publishes them on a separate page,
   https://www.eccb-centralbank.org/contact-information-for-license-financial-institutions-by-country
   (referenced by footnote 2 of the PDF). Not in ticket scope — say if it should be joined in.

---

## Not verified / known gaps

- Only the **current** revision of the register was parsed. No historical revisions checked.
- The revoked-licences PDF was **not** downloaded or parsed.
- The contact-information page was **not** scraped; its structure is unexamined.
- `Typology`, `EntryType`, `InternalID_*`, `LEI Code`, `BIC SWIFT Code`, `RegulationDate`,
  `Zip` are left empty — the source publishes none of them.
- Run on macOS with global `python3` (`requests`, `beautifulsoup4`, `pdfplumber`, `pandas`,
  `openpyxl`, `nbformat`, `nbclient`). Not tested on the Windows production box.

---

## Output

**Eight workbooks**, `<RegCtry> <RegCode> SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, sheet
`SQL Ready`, written to **this folder** (not `tempfolder/`). All eight ECCB members deliver from
`AI ECCBAI/`; no sibling folders are created for the other seven (decided 2026-08-25 — this
scraper owns the whole currency union). 31 rows each, 248 total; 43 columns,
fixed schema, asserted at import time. See *One workbook per regulator* above for the file list
and the `WRITE_COMBINED` option.

ID/Zip/Phone columns are forced to text before writing, and **each** workbook is read back after
writing to assert no value was coerced into scientific notation, the 43-column schema is intact,
and `Name` round-trips as a non-empty string.
