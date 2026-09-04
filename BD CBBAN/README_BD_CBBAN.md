# BD CBBAN — Bangladesh Bank (central bank of Bangladesh)

Jira: **DECD-6975**
Site: https://www.bb.org.bd (English site, `/en/index.php/...`)
Scraper: `BD_CBBAN_v_3.py` / `BD_CBBAN_v_3.ipynb`
Run observed: 2026-09-03 — **109 rows total**, output `BD CBBAN SQL Ready 2026-09-03 11.57.41.xlsx`

---

## Lists

| ListNr | ListCode | ListLabel | ListName (per ticket) | Link text on site | URL | Rows (observed) |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | Banks | Banks | https://www.bb.org.bd/en/index.php/links/links/9 | 63 |
| 2 | 2 | 4 | Financial Institutions | Finance Companies | https://www.bb.org.bd/en/index.php/links/links/2 | 35 |
| 3 | 3 | 4 | Micro Finance Institutions | Micro Finance Institutions | https://www.bb.org.bd/en/index.php/links/links/3 | 5 |
| 4 | 4 | 4 | Others | Others | https://www.bb.org.bd/en/index.php/links/links/4 | 6 |
| | | | | | **TOTAL** | **109** |

`ListName` is stored **verbatim from the ticket**, which is why list 2 is stored as
*Financial Institutions* even though the site's own link text reads *Finance Companies*.

### The ticket's "click on the corresponding list name" comment

The Comments column asks you to click the list name from the links index. Verified live
2026-09-03: the index page (`/en/index.php/links/index`) links each of those names straight
to the `/links/links/<id>` URL **already given in the ticket**, so the ticket URL *is* the
destination page and no click-through step is needed. The index carries three further
categories that are **out of scope** for this ticket and are not scraped: `links/6`
Government, `links/5` International, `links/8` Credit Rating Agency.

### ListLabel justification (1 = bank, 2 = insurance, 3 = both, 4 = other)

- **List 1 = 1** — Bangladesh's scheduled banks (state-owned, private, Islamic, foreign).
- **List 2 = 4** — Bangladesh's "Finance Companies" are **non-bank** financial institutions
  under the Finance Company Act 2023 (formerly the Financial Institutions Act 1993). They are
  BB-licensed but are not banks and not insurers. Same treatment as the Finance Companies
  lists in `NG CBNI` and `PK SBP`. **See judgment call 2 below.**
- **List 3 = 4** — NGO-microfinance institutions (ASA, BRAC, BURO Bangladesh, Jagorani Chakra
  Foundation, Shakti Foundation). These are **not** licensed as banks — contrast `KE CBK` /
  `RW NBRW`, where the category is explicitly "Microfinance *Banks*" and gets 1.
- **List 4 = 4** — research institutes, a scholarship programme and a trade portal.

---

## Site mechanics and quirks

### A real browser is mandatory — `requests` returns a 200 that is not the page

`www.bb.org.bd` sits behind an **F5 / TrustedShield "TSPD" JavaScript bot challenge**.
Measured 2026-09-03 with plain `requests` (Mac, corporate TLS proxy, `verify=False`):

| URL | status | bytes | `<table>` count |
|---|---|---|---|
| `links/links/9` | **200** | 43640 | **0** |
| `links/links/2` | **200** | 48200 | **0** |
| `links/links/3` | **200** | 43757 | **0** |
| `links/links/4` | **200** | 44120 | **0** |

The body is an obfuscated challenge carrying `window["bobcmn"]` and `TSPD_101` cookie
plumbing — no title, no content. **A status-code check calls this a success.** That is
precisely why the scraper's guard is a real parse (`parse_rows()`), never an HTTP check.
Chromium via DrissionPage solves the challenge and the table appears (56714 bytes,
1 table, 64 rows for list 1).

Do **not** "simplify" this back to `requests`. The 403/challenge would return silently as
an empty register.

### Two Chromium traps, both measured on this box

1. **`set_argument('--headless=new')` breaks the DevTools websocket handshake** —
   `websocket._exceptions.WebSocketBadStatusException: Handshake status 404 Not Found`,
   raised inside `ChromiumPage(co)` before any navigation. `ChromiumOptions.headless(True)`
   is the form that works and is what the scraper uses.
2. **Chrome is isolated with `auto_port()` and never with `set_user_data_path()`** —
   `auto_port()` already allocates a throwaway profile; setting both blanks the address and
   Chromium dies on `not enough values to unpack`. (Same note as `AL AFSA` v3.2.)

### Table shape

One `<table>` per page, **no `<thead>`** — the header row (`Organisation` | `Web Link`) is
the first `<tr>` inside `<tbody>`. All four pages ship every row in the initial rendered DOM:
**there is no pagination, no "next" control and no XHR** on any of the four lists. The whole
table is read from a single navigation.

Columns are resolved **by header label**, never by position (`Organisation`/`Name` → name
cell, `Web Link`/`Website`/`URL` → link cell), so an upstream column swap cannot silently
push URLs into `Name`.

### The source publishes only two columns

There is no address, city, phone, licence number, licence date or registration ID anywhere
on these four pages. Most of the 43-key schema is therefore **legitimately empty** — that is
a property of the source, not a scrape gap. See the completeness table below.

### Bracketed status annotation inside the name cell

One entity is annotated by BB inside the name cell itself:

```
Nagad Digital Bank PLC. [Yet not granted permission for Commercial Operation]
```

Left in place this editorial note becomes part of the loaded entity name.
`split_annotation()` splits a **trailing square-bracket** annotation into `License_Type`
and keeps the clean name in `Name`.

**Round parentheses are deliberately left alone.** Audited across all four lists on
2026-09-03: **1** square-bracket annotation vs **10** legitimate `(...)` that are part of the
real name — abbreviations (`(BIFC)`, `(GSPB)`, `(IDCOL)`, `(SABINCO)`, `(JCF)`, `(CPD)`,
`(JDS)`, `(LEIC)`, `(PKSF)`) and one former name
(`BASIC Bank PLC. (Bangladesh Small Industries and Commerce Bank PLC.)`). A rule that
stripped parentheses would corrupt ten names to fix one.

The rule never empties a name: if stripping would leave `Name` blank, the original is kept.

### Console encoding

The Windows control server runs a cp1252 console. Nothing read off the website reaches
`print()` — the log prints counts and ASCII status lines only, and the one helper that could
touch scraped text (`ascii_safe()`) forces `encode('ascii','replace')` first.

---

## Field mapping

| Source | sqldict key |
|---|---|
| `Organisation` cell text (trailing `[...]` removed) | `Name` |
| trailing `[...]` annotation, if any | `License_Type` |
| `Web Link` cell `<a href>` | `Website` |

Constants written on every row: `Cntry='BD'`, `RegCtry='BD'`, `RegCode='CBBAN'`,
`ListCode=<ListNr as string>`, `ListLanguage='EN'`, `RegulationType='Regulated'`,
`Typology=ListName`, `ListName=<ticket ListName>`, `ListLabel` per the table above,
`ListProcessDate=%Y-%m-%d`.

All other keys are empty strings. Every row is written through a single `add_row()` that
appends to **all 43 keys every time**, so the ragged-array `ValueError: All arrays must be
of the same length` that killed v2 cannot occur.

---

## Row-count reconciliation

The site prints no declared total, so the authoritative count is the number of data rows in
the table. The scraper compares rows-seen to rows-kept per list and aborts on any mismatch.

Observed — **every list matched exactly, 109/109, across three independent fetches of the
live site** (a standalone probe, the `.py` run, and the `.ipynb` run):

```
list 1  Banks                      63 / 63
list 2  Financial Institutions     35 / 35
list 3  Micro Finance Institutions  5 /  5
list 4  Others                      6 /  6
TOTAL                             109 / 109
```

The `.py` and `.ipynb` outputs were compared cell-by-cell with `DataFrame.equals` →
**identical**.

**No `drop_duplicates()` anywhere.** As it happens all 109 names are distinct on this run,
but no de-duplication is applied, so a repeat on the site would appear as a repeat here.

### Field completeness (measured on the saved workbook, 109 rows)

| Column | Non-empty | % |
|---|---|---|
| `Name` | 109 / 109 | 100.0 |
| `Website` | 107 / 109 | 98.2 |
| `License_Type` | 1 / 109 | 0.9 |
| `City` | 0 / 109 | 0.0 |
| `Address_1` | 0 / 109 | 0.0 |
| `Phone` | 0 / 109 | 0.0 |
| `InternalID_1` | 0 / 109 | 0.0 |

The two rows without a website are **Nagad Digital Bank PLC.** and
**Sammilito Islami Bank PLC** — both genuinely carry an empty `<td><a href="" target="_blank"></a></td>`
on the site. Verified in the raw HTML; this is not a parse gap.

### Assertions the run passes

- Column list equals the frozen 43-key schema, in order, both before `to_excel` and after
  reading the workbook back.
- `Name` content checked separately from the row count — not blank, not `Yes`/`No`, not the
  header strings `Organisation`/`Web Link`, never starting with `http`/`www` (which would
  mean the column mapping had inverted), length 2–200. Observed range 3–79.
- `InternalID_1..3`, `Phone`, `Fax`, `Zip`, `Zip - Mother company`, `Phone - Mother company`
  forced to text and re-read with `dtype=str`; asserted free of `e+` scientific notation.
- Encoding scan over `Name` + `Website` for `Ã©`, `â`, `Â `, and runs of `?{3,}` — clean.
  0 of 109 names contain a non-ASCII character.
- A list that cannot be parsed after 4 navigations dumps its HTML to
  `tempfolder/FAILED list<n> <timestamp>.html` and the run **refuses to write a workbook**
  rather than shipping a partial file that would de-list every entity in that list.
  No dump was produced on this run.

---

## Judgment calls for the requester

1. **These are "related links" pages, not licensing registers.** The `/links/` section of
   bb.org.bd is a link directory. `RegulationType='Regulated'` is written on all 109 rows per
   the project default, but that is a much better fit for lists 1–2 than for lists 3–4:
   - **List 3 (Micro Finance Institutions)** — MFIs in Bangladesh are licensed by the
     **Microcredit Regulatory Authority (MRA)**, not by Bangladesh Bank. Calling them
     "Regulated" by CBBAN is arguably wrong, and the five named here are a curated sample,
     not the MRA's ~700-entity register.
   - **List 4 (Others)** — contains BIDS Bangladesh and Centre for Policy Dialogue (research
     institutes), Japan Human Resources Development Scholarship (a scholarship programme),
     Local Enterprise Investment Centre, Palli Karma-Sahayak Foundation (an apex
     microfinance *funding* agency) and SAARC Trade Portal (a website, not an entity).
     **None of these are regulated financial institutions.** Flagging rather than guessing —
     confirm whether list 4 should carry `RegulationType='Regulated'`, a different value, or
     be dropped from the load entirely.
2. **List 2 ListLabel = 4.** Bangladesh's Finance Companies are deposit-taking-but-not-banks.
   If the convention is to fold deposit-taking NBFIs into the bank label (as `ZM BZA` list 3
   does), this becomes `1`. Please confirm.
3. **Nagad Digital Bank PLC.** is flagged on the site as *"Yet not granted permission for
   Commercial Operation"*. It is currently written with `RegulationType='Regulated'` and the
   note preserved in `License_Type`. If a not-yet-operating bank should carry a different
   `RegulationType`, say which value. The run prints a `[WARN]` for this row.
4. **`ListValidityDate` is empty** — BB publishes no "as of" date on these pages.
5. **`InternalID_1` is empty on all 109 rows** — the source publishes no identifier of any
   kind. If BB licence numbers are needed they must come from a different section of the site
   (this ticket's four URLs do not carry them).

---

## What was wrong with v1 and v2

Both old notebooks were audited before v3 was written; **neither one runs**.

- **Both point at a retired URL.** v1 and v2 both `driver.get('https://www.bb.org.bd/links/index.php')`
  and then click a `LINK_TEXT`. v2's stored traceback is
  `AttributeError: 'NoneType' object has no attribute 'find'` on
  `soup.find('table').find('tbody')` — `find('table')` returned `None` because the page it
  landed on had no table at all. The live pages are now `/en/index.php/links/links/<id>`.
- **Schema violation: both declare 44 keys, not 43** — an extra trailing `'Check': []`.
  Removed in v3, which asserts the key count and order at import time.
- **v2's `bourange_same_length_array()` padding pass silently corrupted the data.** Its own
  stored output shows `Key 'ListCode' has 216 values` against 108 for every other key —
  `ListCode` was appended to *and* padded, so it double-counted, and
  `pd.DataFrame(sqldict)` then died with `ValueError: All arrays must be of the same length`.
  v3 has no padding pass at all: `add_row()` writes every key exactly once per row.
- **Hard-coded Windows path** in v2:
  `scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"`,
  with the portable line commented out. v3 uses the `try/except NameError` house pattern.
- **`ListLabel` was never populated** in either version.
- **`print(tr.text)` on scraped rows** (v1) — the cp1252 `UnicodeEncodeError` that CLAUDE.md
  warns about. Removed.
- **v1 wrote `sheet_name='SQL ready'`** (lowercase r) and called the long-removed
  `writer.save()`. v3 writes `'SQL Ready'` via a context manager.
- **v2 mislabelled the lists**: it set `ListName` from a `Typology` dict whose values differ
  from the ticket's ListNames, and its `regdict` used the site link text rather than the
  ticket text. v3 stores the ticket ListName verbatim and keeps the site link text only as a
  lookup comment.
- Neither version handled the TSPD challenge deliberately — they happened to use Selenium, so
  a browser was present by accident rather than by design. v3 documents why the browser is
  load-bearing.

---

## Known future breakage risks

- The parser depends on the header labels `Organisation` and `Web Link`. A relabel (e.g. to
  `Institution` / `Website` — both already accepted) is tolerated; anything outside
  `NAME_LABELS` / `LINK_LABELS` makes `parse_rows()` return `None`, which fails **loudly**
  after 4 navigations rather than returning 0 rows.
- The numeric category ids (`9`, `2`, `3`, `4`) come from the ticket. They are opaque and BB
  could renumber them; `links/9` for Banks in particular is out of sequence with `2`/`3`/`4`,
  which suggests the Banks page was re-created at some point.
- The TSPD challenge could be tightened to defeat headless Chromium. If lists start failing
  with `FAILED list<n>*.html` dumps, try `headless(False)` first.
- If BB ever paginates these tables, `parse_rows()` would return only page 1 **without
  error** — the row count would drop silently. The reconciliation compares rows-seen to
  rows-kept, which would not catch it; a human row count against the site is the only guard.

## Not verified

- A run on the Windows control server. Everything above was written and measured on the dev
  Mac with the project `.venv` (Python 3.13.14). In particular the `headless(True)` fix and
  the `auto_port()` isolation are measured **here**, not there.
- Whether Bangladesh Bank publishes a fuller licensing register (with addresses and licence
  numbers) elsewhere on the site — only the four ticket URLs were examined.
- Whether the Bengali version of these pages carries more entities than the English one.
  `ListLanguage='EN'` honestly reflects the pages actually parsed. (`AR BCRA` is the
  precedent for a site whose non-English pages are ahead of the English ones.)
