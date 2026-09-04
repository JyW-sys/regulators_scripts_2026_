# BA KOMVP — Komisija za vrijednosne papire Federacije Bosne i Hercegovine

Jira: **DECD-6830**
Regulator: Securities Commission of the Federation of Bosnia and Herzegovina — the **securities**
supervisor, not the banking one (that is FBA) and not the insurance one (that is AZOBIH).

- Script: `BA_KOMVP_v2.py` (production)
- Notebook: `BA_KOMVP_v2.ipynb` (same code, cells split on the `#---- Begin_XXX ----` markers)
- Output: `BA KOMVP SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, written into this folder, sheet `SQL Ready`
- Reference only, superseded: `BA_KOMVP_v1.ipynb` (Selenium; see *What was wrong with v1*)

Root: `https://www.komvp.gov.ba`

---

## 1. Lists

The ticket defines **three lists**. The *List Code* column was corrected in the ticket on
2026-08-28 from `BA KOMVYP 1/2/3` to plain `1/2/3`; v2 uses `1`, `2`, `3`.

| ListCode | ListName | ListLabel | URL | Rows |
|---|---|---|---|---|
| 1 | List of Issuers | 4 | `/en/market-participants/issuers` | **855** |
| 2 | List of Fund Management Companies | 4 | `/en/market-participants/fmc` | **16** |
| 3 | List of Investment Funds | 4 | `/en/market-participants/funds` | **29** |
| | | | **TOTAL** | **900** |

### ListLabel justification

Repo rule: **1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.**
All three registers are securities-market registers — listed issuers, fund managers, and
investment funds — so all are **4**.

> Caveat for the ticket owner: the *Issuers* register is a list of **companies with publicly
> listed securities**, so it incidentally contains some insurers (e.g. `02-44`
> `"ZOVKO OSIGURANJE" d.d. Žepče`) and other financial firms. `ListLabel` is assigned per list,
> not per entity, and the list itself is a securities register — hence `4`. Flagging in case the
> requester wants those rows re-labelled.

### RegCode

`RegCode = 'KOMVP'`. v1 emitted **`KOMVYP`**, a typo, because it string-split the old
`'BA KOMVYP 1'` dictionary keys. There is no agency called KOMVYP.

---

## 2. How the data is retrieved

Plain `requests` — **no browser**. Two GETs per entity at most:

1. **GET the list page.** It returns *every* row inside `<tbody>` (855 / 16 / 29), with columns
   `ID | Name | Details`. This is the source of truth for how many entities exist and what they
   are called.
2. **GET each detail page** at `/en/market-participants/<slug>/<ID>` and overlay the extra fields.

**The list page drives the output; the detail page is enrichment only.** Every list row becomes
exactly one output row, unconditionally. A detail page that is empty, 404s, or fails to fetch
still yields a row carrying the list-page ID and Name with blank extras. This is the single most
important structural difference from v1 — see §5.

Detail fetching runs in **two phases**: fetch all of them, then re-fetch whatever failed on a
fresh session, and only then build the rows. This is not belt-and-braces — see §6, the proxy
drops a handful of pages on every run.

---

## 3. Field mapping

Detail pages are two-column `<tbody>` tables. Labels are matched on the **exact** first-cell text.

| Detail label | Output field | Note |
|---|---|---|
| `Company Name` | `Name` | falls back to the list-page name when absent |
| — list `ID` column — | `InternalID_1` + `InternalID_1_type='ID'` | e.g. `01-01`, `04-1`, `ZJP-031-1` |
| `Company Identification Number` | `InternalID_2` + `_type` | |
| `Court Registry File Number` | `InternalID_3` + `_type` | |
| `Company type` / `Fund Type` | `CoType` | `Dioničarsko društvo`; `JP - Javna ponuda` for funds |
| `Investment method` | `License_Type` | funds only, e.g. `N - Novčani` |
| `Address` | `Address_1` + `City` | City = segment after the last comma |
| `Phone` / `Fax` / `Web page` | `Phone` / `Fax` / `Website` | |
| `E-mail` | `Email` | Cloudflare-obfuscated, decoded — see §4 |
| `License Issuance` | `RegulationTypeCode` | decision number, e.g. `05/3-19-73/24` |
| `Date License Issuance` | `RegulationDate` | |
| `License withdrawal date` | `CancellationDate` | |
| `Društvo koje upravlja Fondom` | `Name - Mother Company` | the managing company, funds only |

Constants: `Cntry='BA'`, `RegCtry='BA'`, `RegCode='KOMVP'`, `ListLanguage='EN'`,
`RegulationType='Regulated'`, `ListProcessDate = now.strftime('%Y-%m-%d')`.

**Not mapped:** `Short Company Name` (no schema slot), `Fondovi kojim upravlja Društvo` (a child
list of funds under a manager, not a parent), `Date Registry File Number` (junk — renders as
`1/1/1900 12:00:00 AM`).

### RegulationType

Every row is **`Regulated`**, per the ticket owner's instruction. The withdrawal date is still
captured into `CancellationDate` and **no rows are excluded**, so the output row count matches the
site exactly. Note that some names carry a Bosnian status suffix in the source — `- NEAKTIVNO`
(inactive), `- UTVRĐEN PRESTANAK DRUŠTVA` (company wound up), `(BRISANO)` (struck off). These are
left in `Name` verbatim, as published. If the requester later wants withdrawn entities
distinguished, the `License withdrawal date` field is the reliable signal, not the name suffix.

---

## 4. Cloudflare email de-obfuscation

Emails are served as `<a href="/cdn-cgi/l/email-protection" data-cfemail="…">[email protected]</a>`.
v1 stored the literal string `[email protected]`. v2 decodes it — first byte of the hex blob is
the XOR key:

```python
def cfdecode(hexstring):
    key = int(hexstring[:2], 16)
    return ''.join(chr(int(hexstring[i:i+2], 16) ^ key) for i in range(2, len(hexstring), 2))
```

**The lookup must be scoped to the value `<td>`.** Every page also carries the Commission's own
`info@komvp.gov.ba` in the footer as a second `data-cfemail` node; a page-wide
`select('[data-cfemail]')[0]` would be right by luck on entity pages and wrong on the ~35% that
have no entity email, stamping the regulator's address onto those records.

Verified: issuer `01-155` decodes to `hbrzika@gmail.com`, FMC `04-1` to `sib-ar@bih.net.ba`.

---

## 5. What was wrong with v1, and why the numbers move

v1 (`BA_KOMVP_v1.ipynb`, left on disk untouched) had four defects. The first two silently lost
entities, which is why v2 returns substantially more rows.

### 5.1 ~35% of issuers were dropped

v1 appended a record **only when a detail page contained a `Company Name` row**:

```python
if 'Company Name' in tr.text and 'Short Company Name' not in tr.text:
    sqldict['Name'].append(name)      # <- the only place a record was created
```

A large share of issuer detail pages carry **no `Company Name` at all** — they render a single
`('Address', ',')` row. Sampling 40 of the 855 issuer detail pages, **14 (35%) were like this**;
so were 1 of 16 FMC and 5 of 29 funds. Every one of those entities produced no row whatsoever,
even though the list page shows its ID and full name. v2 drives from the list page, so they are
all captured — e.g. `02-44` and `01-549` now appear with their names and blank addresses.

### 5.2 Pagination dropped more rows

The list pages ship all rows server-side; **DataTables paginates client-side only**. v1 drove
Selenium over the `#DataTables_Table_0_next` button — a widget that never gated the data — and
lost rows in the process: its last recorded run captured **15 of 16** FMC and **21 of 29** funds.
v2 issues one GET and reads the complete `<tbody>`.

### 5.3 Substring label matching

v1 used `in tr.text` tests, so `'License Issuance' in tr.text` also matched
`Date License Issuance`, and `'Address'`/`'Phone'` matched loosely. Combined with
`bourange_same_length_array()` — which back-filled short columns with `''` at the end of each
entity — a missed or doubled field silently shifted values onto the wrong rows rather than
failing. v2 matches the first cell exactly and writes **every one of the 43 keys on every row**,
so misalignment is impossible by construction.

### 5.4 Mechanical breakage

- Hard-coded `scriptfolder = "C:\\Users\\wuj1\\OneDrive - moodys.com\\..."` — `FileNotFoundError`
  anywhere but that one machine. v2 uses the `__file__` / `os.getcwd()` try-except.
- `sqldict` carried an **extra `'Check'` key** on top of the project schema's 43. Removed; v2
  asserts `list(df.columns) == SCHEMA_KEYS` before saving, with `SCHEMA_KEYS` copied verbatim
  from the project `CLAUDE.md` block.
- `writer.save()` — removed in pandas ≥ 2.0, raised `AttributeError` at the final cell, so the
  workbook was never written by that run.
- `df.drop_duplicates()` — dropped, it can collapse legitimately similar rows. v2 filters only
  `df['Name'] != ''`.
- v1 printed scraped names to stdout, which throws `UnicodeEncodeError` on the cp1252 console of
  the control server. v2 prints counts only.

---

## 6. Site quirks that will break this scraper later

* **The host is TLS 1.3-ONLY.** Probed per version: TLS 1.0 / 1.1 / 1.2 all fail, 1.3 succeeds.
  Mac system python (LibreSSL 2.8.3) has no TLS 1.3 and can never connect. The script guards this
  at startup and aborts with a clear message rather than producing an empty workbook:

  ```python
  if ssl.OPENSSL_VERSION_INFO < (1, 1, 1):
      raise SystemExit('[FATAL] ... has no TLS 1.3 ...')
  ```

  > **Unverified for production:** the Windows control server runs Python 3.8. Official 3.8
  > Windows builds bundle OpenSSL 1.1.1, which does support TLS 1.3, but that box's environment
  > is messy. Run `python -c "import ssl; print(ssl.OPENSSL_VERSION)"` there before the first
  > scheduled run. If it reports OpenSSL < 1.1.1 the guard will abort, which is the intended
  > behaviour — it is not a scraper bug.

* **Half-open connections through the corporate proxy.** Requests go via a local proxy
  (`127.0.0.1:3636`). A pooled keep-alive connection there can go half-open: the socket stays
  `ESTABLISHED`, the read never returns, and every later request reusing that pooled connection
  inherits the stall. This stalled a full run at 12 minutes for 3 seconds of CPU. `get()` therefore
  **discards the entire session and rebuilds the connection pool** on any transport failure —
  retrying on the same `Session` does *not* clear it. Timeout is `(10, 20)`, deliberately tight
  against an observed ~0.3 s/page.

  Even with that, a run can lose a handful of pages to the proxy: the first full run dropped
  **12 of 855** issuer details. Detail fetching is therefore **two-phase** — fetch everything,
  then sweep the failures once more on a fresh session — and only what fails *twice* is reported
  as lost. Rows are never dropped either way; a lost detail page leaves the row with its
  list-page ID and Name.

* **Client-side pagination** (§5.2) — the most likely thing a future maintainer "fixes" by
  re-adding a browser and a next-button loop. Do not. The rows are already all there.

* **Empty detail pages are normal, not an error** (§5.1). Never treat a missing `Company Name`
  as a reason to skip a row.

* **Two `data-cfemail` nodes per page** (§4) — the second is the regulator's own address.

* **Excel coercion.** `Company Identification Number` values like `4200110170002` become
  `4.2e+12`, and `01332813` / phone `033566750` lose their leading zeros. `InternalID_1/2/3`,
  `Phone`, `Fax` and `Zip` are written with `number_format='@'` and the workbook is **read back
  and asserted** after saving.

* **Field values are Bosnian even on the `/en/` pages.** The *labels* are English (`Company Name`,
  `License Issuance`) but the values are not (`Dioničarsko društvo`, `Društvo koje upravlja
  Fondom`). `ListLanguage` is `EN` because the parsed pages are the English ones.

---

## 7. Run

```bash
python "BA KOMVP/BA_KOMVP_v2.py"
```

Takes roughly 5 minutes: 3 list pages + 900 detail pages at ~0.3 s each plus a 0.15 s courtesy
sleep. Progress prints every 50 pages.

The run ends with a reconciliation block (expected / on site / kept) and aborts non-zero if rows
kept ever differ from rows seen on the site, so a partial scrape cannot quietly produce a
short workbook.

---

## 8. Last verified run — 2026-08-28

`BA KOMVP SQL Ready 2026-08-28 11.29.07.xlsx`, exit 0, ~6 min.

```
   issuers      855 /   855 /   855
   fmc           16 /    16 /    16
   funds         29 /    29 /    29
   TOTAL        900 /   900 /   900
```

Retry sweep recovered 12 issuer and 1 fund detail pages; **0 detail fetches failed** overall.

Checked in the saved workbook: 900 rows × 43 columns matching `SCHEMA_KEYS`; `RegCode` `KOMVP`
and `RegCtry` `BA` on all rows; `ListCode` 855/16/29; `ListLabel` 4; `RegulationType` `Regulated`;
no duplicate `InternalID_1` within a list; no empty or `Yes`/`No` `Name`; `01-01` and 481 phone
numbers still text with leading zeros intact and no scientific notation; `01-155` →
`hbrzika@gmail.com`, **0** rows carrying the footer `info@komvp.gov.ba`, 0 literal
`[email protected]`; `02-44` and `01-549` (empty detail pages) both present with real names;
`04-1` carries `CancellationDate 14.07.2022.` with `RegulationType` still `Regulated`;
`JP-N-032-6` carries its managing company.

### Expected blanks — do not treat as extraction failures

* **Funds carry no contact details.** Fund detail pages have only `Company Name`,
  `Short Company Name`, `Fund Type`, `License Issuance`, `Društvo koje upravlja Fondom`,
  `Court Registry File Number`, `Date Registry File Number` and sometimes `Date License Issuance` /
  `Investment method` — verified against the live pages. So all 29 funds have blank
  `Address_1` / `City` / `Phone` / `Fax` / `Email` / `Website`.
* **Issuers carry no licence dates** — `RegulationDate` and `CancellationDate` are blank for all
  855; those fields only exist on the FMC and fund registers.
* **383 of 855 issuers have an empty detail page** (§5.1) — name and ID from the list page only.
* Always blank, no source on this site: `bvdid`, `priority`, `Typology`, `EntryType`,
  `Address_2`, `Zip`, `ListValidityDate`, `LEI Code`, `BIC SWIFT Code`, and every
  `* - Mother company` column except `Name - Mother Company`.
