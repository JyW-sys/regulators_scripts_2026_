# BB BFSC — Financial Services Commission, Barbados

**Jira:** DECD-6820 (epic DECD-3438, Regulators 2026 — Crawlers)
**RegCtry:** `BB`  **RegCode:** `BFSC`  **ListLanguage:** `EN`
**Entry point:** https://www.fsc.gov.bb/regulated-entities

Files:

| File | What it is |
|---|---|
| `BB_BFSC_v1.py` | the scraper (production, runs as `python3 BB_BFSC_v1.py`) |
| `BB_BFSC_v1.ipynb` | the same code split into `Begin_Librairie / fileName / Variable / Function / MainLoop / writer` cells, generated from the `.py` and executed end-to-end |
| `BB BFSC SQL Ready <timestamp>.xlsx` | output, sheet `SQL Ready`, 43 columns (fixed project schema) |
| `tempfolder/` | the three downloaded PDFs (`securities.pdf`, `creditunions.pdf`, `insurance.pdf`) |

---

## Lists (from the Jira description)

| ListNr | ListName | ListLabel | URL | Published as | Jira comment | Rows scraped |
|---|---|---|---|---|---|---|
| 1 | List of Securities | 4 | https://www.fsc.gov.bb/regulated-entities | PDF (2 landscape pages, ruled table) | Collect companies; if the name contains "inactive", do NOT collect it | **145** |
| 2 | List of Credit Unions | 4 | https://www.fsc.gov.bb/regulated-entities | PDF (1 portrait page, no ruling lines) | — | **23** |
| 3 | List of Insurances | 2 | https://www.fsc.gov.bb/regulated-entities | PDF (46 portrait pages, sectioned) | Do NOT collect Class 3 Agent, Class 3 Sub-Agents and Class 3 Salesmen | **364** |
| | | | | | **Total** | **532** |

Counts above are from the actual run on **2026-08-20** against the **July 31, 2026** files
(`ListValidityDate = 2026-07-31` on every row).

---

## How the lists are published & how links are resolved

The landing page is plain server-rendered HTML — no JS, no Cloudflare, `requests` + BeautifulSoup
is enough (`verify=False` for the corporate TLS proxy). Inside `<div id="pageContent">` there is one
`<ul>` with four PDF links, one per FSC division:

```
Pensions - July - 2026        (out of scope for this ticket)
Securities - July - 2026      -> ListNr 1
Credit Unions - July - 2026   -> ListNr 2
Insurance - July - 2026       -> ListNr 3
```

The hrefs are timestamped upload paths that change on every quarterly re-upload, e.g.
`/viewPDF/documents/2026-08-05-12-55-16-Securities---List-of-licensed-entities---as-at-July-31-2026.pdf`.
`resolve_pdf_links()` therefore matches on the **anchor label text** (`securities`, `credit union`,
`insurance`), restricted to `#pageContent` anchors whose href contains `.pdf`. Nothing about the file
name is hard-coded. If the FSC renames a label the run prints
`SKIPPED - no anchor whose label contains '<keyword>'` instead of silently producing 0 rows.

All three PDFs have a real text layer — **no OCR needed**, parsed with `pdfplumber`.

---

## Per-list parsing notes

### List 1 — Securities (`securities.pdf`)

A landscape spreadsheet export with ruling lines. `page.find_tables()` yields one table per
registration category, plus a final `STATISTICAL SUMMARY` table (skipped for entities, but its
numbers are parsed and printed for reconciliation).

* **Column 0 is the company**; the other columns are the natural persons (Brokers, Traders,
  Investment Advisers, Dealers) registered *for* that company. Per the Jira comment
  ("Collect companies") **only column 0 is collected** — the 42 brokers, 13 traders, 40 individual
  investment advisers and 12 individual dealers are deliberately not in the output.
* `page.extract_table()` is **not** used: it silently drops entities sitting on a row whose
  left-hand cell was not detected (observed: *Quantas Advantage Inc.* in Reporting Issuers).
  `column_entries()` rebuilds the column from cell geometry instead, with a per-physical-line
  fallback for those gap rows, and it keeps wrapped names together
  (e.g. `CIBC Caribbean Wealth Management Bank (Barbados) Limited (formerly FirstCaribbean …)`).
* Cell text is read with `page.crop(...).extract_text()`, not by joining `extract_words()` —
  the latter injects spurious spaces inside words (`"s ub-funds"`).

### List 2 — Credit Unions (`creditunions.pdf`)

One page, **no ruling lines at all**, so it is parsed line-wise: every data line is
`<Registration No.> <Credit Union Name>` (regex `^(\d{1,6})\s+(\S.*)$`). The registration number goes
to `InternalID_1` (`InternalID_1_type = 'Registration Number'`).

Quirk: the page ends with a stray leftover heading **`COMBINATION/HYBRID PENSION PLANS (DB + DC)`**
(a copy-paste remnant from the Pensions template). It is ignored because it does not start with a
registration number.

### List 3 — Insurance (`insurance.pdf`)

46 pages, one section per licence category. Section titles are bold, >18 pt and start with
`REGISTERED `/`STATISTIC`. Entity names are the non-bold ~12 pt lines; page header
(`WWW.FSC.GOV.BB`), `No. of licensees: N`, the bold `… - Class N Licence` descriptor, the `NAME`
column header and the footer `31-July-2026 <n> Financial Services Commission` are filtered out.

* **Excluded per Jira:** any section whose title contains `AGENT` or `SALESM` — i.e.
  `REGISTERED INSURANCE AGENTS` (65), `REGISTERED INSURANCE SUB-AGENTS` (0),
  `REGISTERED INSURANCE SALESMAN` (674). The run prints one `skipping section` line for each.
* **DORMANT sub-lists:** Class 1 and Class 2 each end with a bold `DORMANT` sub-heading.
  Those entities **are** part of the FSC's own `No. of licensees` figure, so they are collected and
  flagged in `License_Type` (`… - Dormant`): 1 in Class 1, 5 in Class 2. See "judgment calls" below.

---

## Column mapping

| Output column | Source |
|---|---|
| `Name` | entity name (column 0 of the securities tables / name column of the CU + insurance PDFs) |
| `License_Type` | the category the entity is listed under — see the breakdown below |
| `InternalID_1` / `InternalID_1_type` | Credit Unions only: `Registration No.` / `'Registration Number'` |
| `Name - Mother Company` | Securities sub-funds only: the parent mutual fund (17 rows) |
| `Cntry`, `RegCtry` | `BB` |
| `RegCode` | `BFSC` |
| `ListCode` | 1 / 2 / 3 (the Jira ListNr) |
| `ListLabel` | 4 / 4 / 2 |
| `ListName` | `List of Securities` / `List of Credit Unions` / `List of Insurances` |
| `ListLanguage` | `EN` |
| `ListValidityDate` | parsed from each PDF's own as-of line (`as at July 31, 2026` / `JULY 31, 2026`) → `2026-07-31` |
| `ListProcessDate` | `datetime.datetime.now().strftime('%Y-%m-%d')` |
| `RegulationType` | `Regulated` (all three are positive/authorised registers) |
| everything else | `''` — the PDFs carry **no** address, city, phone, website, email, LEI or registration date. The securities PDF has `Registration date (new registrant)` columns but they are empty in the July 2026 file, so `RegulationDate` is left blank. |

`add_row()` appends to **every** key of `sqldict` on every record and raises on an unknown key, so
the 43 columns can never drift out of alignment.

---

## Row counts vs. what the FSC itself publishes (reconciliation)

Both the Securities and the Insurance PDFs print their own totals, and the scraper parses and prints
them next to the scraped counts at the end of every run.

### List 1 — Securities (145)

| Category (`License_Type`) | FSC STATISTICAL SUMMARY | scraped |
|---|---|---|
| Self-Regulatory Organisations (SROs) | 6 | 6 ✅ |
| Securities Company | 21 | 21 ✅ |
| Investment Adviser | 22 | 22 ✅ |
| Dealers | 7 | 7 ✅ |
| Underwriters | 5 | 5 ✅ |
| Reporting Issuers (listed and unlisted companies) | 39 | 39 ✅ |
| Other issuers with registered securities (…) | 3 | 3 ✅ |
| Mutual Funds (including sub-funds) — parent funds | 15 (*"Mutual Funds (Excluding Sub-Funds)"*) | 15 ✅ |
| Mutual Funds (including sub-funds) - Sub-Fund | — | 17 ⚠️ |
| Mutual Fund Administrator (General) | 7 | 7 ✅ |
| Mutual Fund Administrator (Restricted) | 3 | 3 ✅ |
| **Total** | | **145** |

Not collected (individuals, per "Collect companies"): Broker 42, Trader 13,
Investment adviser (individuals) 40, Dealer (individuals) 12.

### List 2 — Credit Unions (23)

The PDF publishes no count. 23 numbered lines on the page, 23 rows scraped ✅.

### List 3 — Insurance (364)

| Section | FSC `No. of licensees` | scraped |
|---|---|---|
| REGISTERED INSURANCE CLASS 1 COMPANIES | 168 | 167 + 1 dormant = 168 ✅ |
| REGISTERED INSURANCE CLASS 2 COMPANIES | 125 | 120 + 5 dormant = 125 ✅ |
| REGISTERED INSURANCE HOLDINGS COMPANIES | 8 | 8 ✅ |
| REGISTERED INSURANCE MANAGEMENT COMPANIES | 15 | 15 ✅ |
| REGISTERED ASSOCIATION OF UNDERWRITERS | 1 | 1 ✅ |
| REGISTERED INSURANCE BROKERS | 23 | 23 ✅ |
| REGISTERED INSURANCE ADJUSTERS | 10 | 10 ✅ |
| REGISTERED INSURANCE LOSS ASSESSORS | 2 | 2 ✅ |
| REGISTERED INSURANCE SURVEYORS | 12 | 12 ✅ |
| REGISTERED INSURANCE AGENTS | 65 | **not collected** (Jira) |
| REGISTERED INSURANCE SUB-AGENTS | 0 | **not collected** (Jira) |
| REGISTERED INSURANCE SALESMAN | 674 | **not collected** (Jira) |
| **Total collected** | **364** | **364** ✅ |

---

## Judgment calls / open questions for the reviewer

1. **Mutual fund sub-funds are included** (17 rows, `License_Type = 'Mutual Funds (including
   sub-funds) - Sub-Fund'`, parent in `Name - Mother Company`). The FSC's own category is literally
   named *"Mutual Funds (including sub-funds)"*, so sub-funds are registered entities.
   ⚠️ The FSC's summary number for that category is **25**, but the list actually contains
   **15 funds + 17 sub-funds = 32**. The FSC's own two figures (25 "including sub-funds" vs 15
   "excluding sub-funds") are mutually inconsistent with the printed list; 15 and 17 are what is
   really on the page. Drop the 17 sub-fund rows if only top-level companies are wanted.
2. **`Investment Advisers Registered on Behalf of The Bank of Nova Scotia`** is how the Investment
   Adviser table labels its 22nd company row (six individuals are listed under it).
   `normalise_securities_name()` strips the `… Registered on Behalf of ` prefix so the row is stored
   as **`The Bank of Nova Scotia`**. This is what makes the section reconcile with the FSC's own
   count of 22. Remove that helper if verbatim text is preferred.
3. **Dormant insurers are included** (1 Class 1 + 5 Class 2), flagged with `- Dormant` in
   `License_Type` and still `RegulationType = 'Regulated'`. They are inside the FSC's licensee
   counts, so excluding them would break the 168/125 reconciliation. Easy to filter on
   `License_Type` if the reviewer wants them out or wants a different `RegulationType`.
4. **The "inactive" filter fired 0 times.** The July 2026 Securities PDF contains no entity whose
   name contains "inactive" (grep across all three PDFs also finds none). The filter is implemented
   and applied to all three lists, and prints every name it drops, so it will work when the FSC
   starts marking entities that way again.
5. **No addresses/contact data anywhere.** The FSC publishes name-only registers; the insurance
   Agents section is the only one with a second column (associated insurer) and it is out of scope.

---

## Environment

macOS, system `python3` (3.9, user site-packages). Requires `requests`, `beautifulsoup4`, `pandas`,
`openpyxl`, `pdfplumber` (0.11.8 used here); `nbformat` + `nbclient` only to regenerate/execute the
notebook. `pdfplumber` prints harmless
`Cannot set gray non-stroke color because /'P121' is an invalid float value` warnings on the
insurance PDF — they do not affect extraction.
