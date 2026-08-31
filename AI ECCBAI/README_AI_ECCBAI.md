# AI ECCBAI — Eastern Caribbean Central Bank

**Jira:** DECD-6832 — AI ECCBAI
**Regulator:** Eastern Caribbean Central Bank (ECCB)
**RegCtry:** `AI` · **RegCode:** `ECCBAI` · **ListLanguage:** `EN`
**Run:** `python3 AI_ECCBAI_v1.py` (or open `AI_ECCBAI_v1.ipynb`)

The ECCB is the shared central bank of eight Eastern Caribbean member territories. The ticket
is filed under Anguilla (`AI`), but its comment says *"collect all entities and addresses from
the different countries"*, so **all eight territories are scraped**. `RegCtry`/`RegCode` stay
`AI`/`ECCBAI`; `Cntry` varies per row and carries the territory each institution is licensed in.

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | Licensed Finance Companies | https://www.eccb-centralbank.org/register-of-licensed-financial-institutions | PDF (`pdfplumber`, ruled table) | **31** |

**ListLabel = 1 (bank).** The register is issued under **section 13(1) of the Banking Act, 2015**
and contains commercial banks, non-bank credit institutions and bank holding companies. It is a
banking-sector register with no insurance content, so `1` rather than `3` or `4`.

**ListValidityDate = `2026-06-25`**, parsed from the anchor label (`… Banking Act 25.6.26`) with
the upload-date stamp in the href as fallback.

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
| country section heading | `Cntry` | ISO-2 of the territory |
| — | `RegulationType` | `Regulated` (positive register) |
| — | `RegCtry` / `RegCode` / `ListLanguage` | `AI` / `ECCBAI` / `EN` |
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
number and compares it with the rows it produced. Output of the actual run:

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

`AI ECCBAI SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, sheet `SQL Ready`, written to this folder
(not `tempfolder/`). 43 columns, fixed schema, asserted at import time.

ID/Zip/Phone columns are forced to text before writing, and the workbook is **read back after
writing** to assert no value was coerced into scientific notation and that `Name` round-trips as
a string.
