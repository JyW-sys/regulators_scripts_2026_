# ID OJK — Otoritas Jasa Keuangan (Indonesia Financial Services Authority)

Jira: **DECD-6836**  ·  RegCtry `ID`  ·  RegCode `OJK`

Production scraper: **`ID_OJK_v2.py`**  ·  Notebook: **`ID_OJK_v2.ipynb`**

---

## Status — run live on 2026-09-03

`www.ojk.go.id` **is** reachable and the scraper **has** been run against it. An earlier version
of this document carried a banner saying the opposite ("NOT YET RUN AGAINST THE LIVE SITE",
"unreachable from the development Mac"); that finding no longer holds and the banner has been
removed. Measured again on 2026-09-03: `curl` returns **HTTP 200** in ~1 s, and ten of the
thirteen lists were resolved and parsed end-to-end from the live site on that date.

`requests` alone was sufficient throughout — including every ASP.NET postback. The
DrissionPage/Chromium fallback was never needed and therefore remains **unexercised**.

### Verified row counts (live, 2026-09-03)

| ListNr | ListName | Rows | Source resolved |
|---|---|---|---|
| 1 | Commercial Banks and Sharia Banks | **105** | `Daftar Alamat Kantor Pusat Bank Umum Dan Syariah - Juni 2026.xlsx` |
| 2 | Representative Offices of Foreign Banks | **22** | inline HTML table |
| 3 | Rural Bank (BPR) | **1252** | `Daftar Alamat Kantor Pusat BPR - Juni 2026.xlsx` |
| 4 | Sharia Rural Banks (BPRS) | **174** | direct `.xlsx` link |
| 5 | Securities Company | **133** | `Data Perusahaan Efek` (2 sheets) |
| 6 | Capital Market Players | **1676** | 12 folders, see the breakdown below |
| 7 | Insurance Companies | **148** | `Direktori Asuransi Triwulan III 2025.xlsx` |
| 8 | Guarantee Companies | *not measured* | — |
| 9 | Pension Funds | *not measured* | — |
| 10 | Insurance / Reinsurance Brokers, Loss Adjusters | *not measured* | — |
| 11 | Financing Institutions | **193** | `Direktori Lembaga Pembiayaan dan PMV` (PDF) |
| 12 | Microfinance Institutions | **235** | `Direktori LKM per 30 Juni 2026.pdf` |
| 13 | Digital Financial Asset Trading Providers | **32** | 6-page poster PDF |

**Lists 8, 9 and 10 have never been fetched from the live site** — not by me, not on any date.
Their counts are unknown; the earlier *(v1)* figures in this file were the previous notebook's
stored output and have been removed rather than restated as if verified. Their code path
(Pattern C) is the same one lists 5, 7, 11 and 12 exercise successfully, so they are *expected*
to work — expected, not shown.

### Request discipline

**Do not debug against the live site.** Set `OJK_CACHE=1` and every page, file and postback
response is written to `tempfolder/httpcache/` on first fetch and read from disk thereafter, so
a parser can be re-run any number of times at zero cost to OJK. It is opt-in precisely so a
scheduled production run can never serve stale data by accident; delete `tempfolder/httpcache`
to force a refetch. The offline self-test needs no network at all.

This matters operationally, not just aesthetically: a debugging loop generates an order of
magnitude more traffic than the production run it is debugging, and the company's cyber security
team has already raised scraping volume with the team once.

---

## Lists

OJK publishes 13 separate directories across three site channels (`perbankan` = banking,
`pasar-modal` = capital markets, `iknb` = non-bank financial industry, plus the newer
`Fungsi-Utama` sections). They do **not** share a format: three are a bare `.xlsx` link, one is
an inline HTML table, eight are an archive index of dated article pages, and one is a
**three-level** folder tree.

| ListNr | ListCode | ListLabel | Source format |
|---|---|---|---|
| 1 | 1 | 1 | direct `.xlsx` link on landing page |
| 2 | 2 | 1 | **inline HTML table** |
| 3 | 3 | 1 | direct `.xlsx` link on landing page |
| 4 | 4 | 1 | direct `.xlsx` link on landing page |
| 5 | 5 | 4 | article index → article → postback download |
| 6 | 6 | 4 | **folder tree, up to three levels** → file |
| 7 | 7 | 2 | article index → article → postback download |
| 8 | 8 | 4 | article index → article → postback download |
| 9 | 9 | 4 | article index → article → postback download |
| 10 | 10 | 2 | article index → article → postback download |
| 11 | 11 | 4 | article index → article → **PDF** download |
| 12 | 12 | 4 | article index → article → **PDF** download |
| 13 | 13 | 4 | article index → article → **PDF** download |

`ListLanguage = 'ID'` for all 13 — every source is the Indonesian (`/id/`) site, with Indonesian
column headers (`Nama`, `Alamat`, `No. Telepon`, `Kota/Kabupaten`, `Provinsi`).

`ListCode` is the ListNr as a plain string (`'1'` … `'13'`). It is pinned to text on write-out
so Excel cannot turn it into a float.

### Row counts move with the edition — this is not a bug

Two counts were queried against the ticket. Both are edition drift, and neither needed a code
change:

- **List 3 — reported 1313, we now emit 1252.** The live file on 2026-09-03 is
  `Daftar Alamat Kantor Pusat BPR - Juni 2026.xlsx`, whose `BPR` sheet is 1253 rows including
  the header. 1252 is that file read correctly. 1313 was an earlier monthly edition.
- **List 12 — reported 235 in the PDF, we emitted 237.** The live file is
  `Direktori LKM per 30 Juni 2026.pdf` and the parser now returns **235** from it.

OJK republishes these directories monthly and the population genuinely changes. **A count
mismatch against a PDF someone downloaded on a different date is expected**; re-resolve the
source before treating it as a parser fault.

- **List 7's source is a year stale at OJK's end.** The newest article on the insurance index is
  `Direktori Asuransi Triwulan III 2025` — OJK has published nothing newer. It parses to 148
  rows. There is no corresponding recent file to find; this is a source-side gap, not a
  discovery failure.

### CoType per list

`CoType` is a per-list constant, since no source file carries an entity-type column that is
consistent across lists:

| ListNr | CoType |
|---|---|
| 1 | Commercial Bank / Sharia Bank |
| 2 | Representative Office of Foreign Bank |
| 3 | Rural Bank (BPR) |
| 4 | Sharia Rural Bank (BPRS) |
| 5 | Securities Company |
| 6 | Capital Market Player *(sub-category appended, see below)* |
| 7 | Insurance Company |
| 8 | Guarantee Company |
| 9 | Pension Fund |
| 10 | Insurance / Reinsurance Broker / Loss Adjuster |
| 11 | Financing Institution |
| 12 | Microfinance Institution |
| 13 | Digital Financial Asset Trading Provider |

`License_Type` is **not** a constant — where the source carries a finer classification it is
carried through. Three verified cases:

- **List 1** — the workbook has no type column; it uses *section header rows* (a single
  populated cell spanning the row): `BANK UMUM PERSERO`, `BANK UMUM SWASTA NASIONAL`,
  `BANK PEMBANGUNAN DAERAH`, `KANTOR CABANG BANK YANG BERKEDUDUKAN DI LUAR NEGERI`. The parser
  tracks the current section into `License_Type`. **These rows are data, not junk.**
- **List 6** — the folder path is the licence kind.
- **List 11** — five financing categories, verified on the live file: `Perusahaan Pembiayaan`
  141, `… Syariah` 3, `Modal Ventura` 42, `Modal Ventura Syariah` 6, `Infrastruktur` 1 = 193.

### ListLabel justification — ALL THIRTEEN STILL NEED CONFIRMATION

The ticket does not specify ListLabel. The values above are my application of the house rule
(1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else):

- **Lists 1, 3, 4 → `1`.** Commercial banks, sharia banks, and the two rural-bank tiers. BPR and
  BPRS are deposit-taking banks under the Indonesian Banking Act, not microfinance.
- **List 2 → `1`.** Representative offices of foreign banks. The *entity* is a bank.
- **List 7 → `2`.** Life, general, reinsurance, compulsory and social insurers.
- **List 10 → `2`.** Insurance intermediaries, not risk carriers. `4` is arguable. **Flagged.**
- **List 8 → `4`. Least confident.** *Perusahaan Penjaminan* sit under OJK's insurance
  directorate and sell a product close to surety insurance, so `2` is defensible. I chose `4`
  because they are licensed under the Guarantee Law (UU 1/2016). **Flagged.**
- **Lists 5, 6, 9, 11, 12, 13 → `4`.** None is a bank or an insurer.
- **`3` is not used** — no single list mixes banks and insurers.

---

## How each list is reached at runtime

**The single most important rule for this regulator: no filename, no article URL, and no period
is ever hard-coded.** OJK republishes every directory under a new name each period, and the
previous scraper broke on exactly this. Everything is discovered on each run.

### Pattern A — direct `.xlsx` link (lists 1, 3, 4)

The landing page's content `<div>` holds exactly one link, pointing straight at the workbook.
OJK replaces that link in place, so "most recent" needs no resolution. The period is read out of
the link text (`… - Juni 2026.xlsx`) purely to populate `ListValidityDate`.

### Pattern B — inline HTML table (list 2)

The only list with no download: one `<table>`, 4 columns `No. | Nama | Alamat | Telepon`,
22 entities plus 13 **country group headers** (single-cell rows: `JEPANG`, `INDIA`, `AMERIKA`,
`BELANDA`, `PERANCIS`, `JERMAN`, `UNI EMIRAT ARAB`, `SPANYOL`, `KOREA SELATAN`, `TAIWAN`,
`THAILAND`, `ITALIA`, `CHINA`) and blank spacers. Parsing notes, all from observed data:

- Cells are riddled with **U+200B zero-width spaces**. Strip `​`/`﻿`/NBSP first, or
  both the country map and the blank-row test fail.
- The `Telepon` column often carries the fax too, in several spellings
  (`(021) 57905399; FAX (021) 57905400`, `… Faks: …`, `… FAX : (021)    29859889`). Split on
  `FAX`/`FAKS`/`FAKSIMILI`.
- `-` means "not published" and must become empty, not a literal dash.
- The office is in Jakarta → `Cntry = 'ID'`; the country group header is the **home country of
  the parent bank** → `Cntry - Mother company`. **See NEEDS CONFIRMATION.**

### Pattern C — article index → article page → postback download (lists 5, 7–13)

The landing page is an archive index of dated article pages. **Position 0 is not reliably the
newest** and must not be used — list 9's index is not monotonic, and list 13 puts a non-list PDF
at position 0. The scraper parses the Indonesian period out of each link text and takes the
maximum:

| Form | Example | Resolves to |
|---|---|---|
| `Triwulan <roman> <year>` | `Triwulan III 2025` | 2025-09-30 |
| `Triwulan <roman> Tahun <year>` | `Triwulan II Tahun 2024` | 2024-06-30 |
| `<Month> <year>` | `Desember 2025` | 2025-12-31 |
| `Posisi <d> <Month> <year>` | `Posisi 21 April 2026` | 2026-04-21 |
| `YYYYMMDD` in a filename | `20241108 Penyelenggara SCF Berizin.pdf` | 2024-11-08 |
| `DDMMYY_` in a filename | `310126_Statistik Notaris.pdf` | 2026-01-31 |

The last two were added on 2026-09-03 for list 6's leaf files, which carry no spelled-out date at
all. Both validate the result as a real calendar date, so a decree or licence number of the same
length cannot be mistaken for one. They sit **below** the spelled-out rules: a date written in
words is always the better evidence.

**The period is read from the link text, never the href.** Verified: the entry reading
`… Posisi 14 Januari 2026` has href `…-Posisi-14-Januari-2025.aspx`. The href year is wrong.

**List 13 needs an extra keyword filter.** Its index interleaves two series plus a criteria
document at position 0; only links matching `Perdagangan Aset Keuangan Digital` are kept.

#### The download button — there is no href

On the article page the file is an ASP.NET WebForms submit input, not an anchor:

```html
<div id="div-download-counter">
  <span class="download-counter-1">
    <input type="submit" class="download-counter"
           name="ctl00$PlaceHolderMain$…$btnDownload"
           value="Direktori Asuransi Triwulan III 2025.xlsx">
  </span>
</div>
```

`value` is the filename, `name` is the postback target. The download is reproduced with plain
`requests` by echoing every hidden input (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`,
`__EVENTVALIDATION`, `__REQUESTDIGEST`) and adding `name=value`. **Verified live on 2026-09-03** —
SharePoint accepted the replayed digest; no browser was needed. An article may expose several
buttons and all are downloaded.

### Pattern D — the list 6 folder tree

List 6 is **not** a two-level tree, which is what the previous version assumed and why the whole
list came back empty. It is up to **three** levels, and the three levels use **two different**
JavaScript wrappers.

**Level 1** — the landing page's first `<ul>` is five folders, each a bare `__doPostBack`:

```
Ahli Syariah Pasar Modal          ctl00$PlaceHolderMain$ctl01$ListViewArticles$ctrl0$listFolder
Lembaga Penunjang Pasar Modal     …$ctrl1$listFolder
Pelaku Perorangan Pasar Modal     …$ctrl2$listFolder
Profesi Penunjang Pasar Modal     …$ctrl3$listFolder
Securities Crowd Funding          …$ctrl4$listFolder
```

**Level 2** — three of those five hold *more folders* and no articles of their own. A one-level
descent therefore found nothing under them.

**Leaf** — the file is an anchor, but not a normal one:

```
javascript:WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions(
    "ctl00$PlaceHolderMain$ctl01$ListViewArticles$ctrl0$listFolder", "", false, "",
    "https://www.ojk.go.id/…/Pelaku%20Perorangan%20Pasar%20Modal/Agen%20Penjual%20Efek%20Reksa%20Dana/Data%20APERD.xlsx",
    false, true))
```

The folder-link regex does not match it (there is no `__doPostBack`) and the article-link matcher
rejects it (the href is `javascript:`, not `.aspx`), so it read as "no article links". But the
**5th positional argument of `WebForm_PostBackOptions` is an absolute URL to the file** — so no
third postback is needed; a straight GET fetches it.

The scraper now walks the tree breadth-first and, at every node, tries the three shapes cheapest
first: a file link → an article page → more folders.

Three further quirks, all found live:

- **`Profesi Penunjang Pasar Modal` files each profession by year**, 2019 through 2026. Only the
  newest year is the current register; the older folders are the same register at earlier dates.
  Descending into all eight would emit every person eight times, so a folder whose children are
  *all* bare years contributes only its newest. The year is a vintage, not a category, so it does
  **not** join the `CoType` label.
- **`Profesi Penunjang Pasar Modal / Akuntan` is empty at OJK's end** — the page says
  "No Article Available". That is not a scrape failure and is no longer reported or dumped as
  one.
- **Filenames beginning `Statistik` are still registers.** `310126_Statistik Notaris.pdf` is 28
  pages headed *"DAFTAR NOTARIS YANG TERDAFTAR DI OTORITAS JASA KEUANGAN"* — a full name-by-name
  list, not aggregate statistics. Do not skip a file on its name.

#### List 6 scope and the live breakdown

Ticket owner's instruction (Guilherme Strelow Hilger, 2025-12-03):

> *"In the individual capital market player, indeed you can extract the companies from the first
> 3 subcategories and Subcategory 1 from the 3 sheets. The last subcategory you can skip."*

Implemented literally for `Pelaku Perorangan Pasar Modal`: the first three sub-folders are taken,
`Wakil Agen Penjual Efek Reksa Dana` is skipped by name, and `Data APERD.xlsx` is read across
**all three** of its sheets. Live on 2026-09-03, **1676 rows** in twelve folders:

| Folder | Rows | File |
|---|---|---|
| Profesi Penunjang / Konsultan Hukum | 493 | `310126_Statistik Konsultan Hukum.pdf` |
| Profesi Penunjang / Notaris | 407 | `310126_Statistik Notaris.pdf` |
| Profesi Penunjang / Penilai | 385 | `Statistik Penilai Per 31 Januari 2026.pdf` |
| Pelaku Perorangan / Manajer Investasi | 96 | `Data Manajer Investasi.xlsx` |
| Ahli Syariah Pasar Modal | 95 | `ASPM Orang Perseorangan.xlsx` |
| Pelaku Perorangan / Agen Penjual Efek Reksa Dana | 88 | `Data APERD.xlsx` — 35 + 33 + 20 across 3 sheets |
| Pelaku Perorangan / Penasihat Investasi | 41 | `Data Penasehat Investasi.xlsx` |
| Lembaga Penunjang / Bank Kustodian | 28 | `Bank Kustodian.xlsx` |
| Securities Crowd Funding | 18 | `20241108 Penyelenggara SCF Berizin.pdf` |
| Lembaga Penunjang / Wali Amanat | 12 | `Daftar Wali Amanat.xlsx` |
| Lembaga Penunjang / Biro Administrasi Efek | 9 | `Daftar Biro Administrasi Efek.xlsx` |
| Lembaga Penunjang / Pemeringkat Efek | 4 | `Data Pemeringkat Efek.xlsx` |
| Pelaku Perorangan / Wakil Agen Penjual Efek Reksa Dana | *skipped* | out of scope per the ticket |
| Profesi Penunjang / Akuntan | *empty* | nothing published by OJK |

**1380 of those 1676 rows are natural persons, not companies** — the three `Profesi Penunjang`
professions (1285) plus `Ahli Syariah Pasar Modal`, whose file is literally named
*ASPM Orang Perseorangan*, "individual persons" (95). The one scope ruling on the ticket excluded
an individual register (`Wakil …`) from a different folder, which suggests these may be out of
scope too — but the ruling does not cover them, so they are **included and flagged** rather than
dropped on my own judgement. **See NEEDS CONFIRMATION.** Excluding them would leave 296 rows.

---

## Parsing rules that were added on 2026-09-03

### List 5 — revoked licences are appended to the same sheet

`Data Perusahaan Efek` does not put revoked firms in a separate file. It appends them to the
**bottom of the same sheet**, under their own heading and a repeated column header. Verified on
the live workbook:

- sheet `Perusahaan Efek`: `Cabut Izin Usaha Pada Tahun 2025` at row 122 (5 firms) and
  `… Tahun 2026` at row 131 (3 firms);
- sheet `PPE Khusus`: `Cabut Izin Usaha Pada Tahun 2025` at row 29, and one firm below it.

All of these were being emitted as `Regulated`. Everything from such a heading down is now
dropped, which also disposes of the repeated header row underneath it. The rule is guarded on
"a row with at most 2 populated cells", so a company whose *name* contained the words could never
truncate the parse. **133 rows, was 149.** The workbook's own numbering confirms it:
`Perusahaan Efek` runs 1…112 and `PPE Khusus` 1…20, and 112 + 20 = 132 + 1 unnumbered = 133.

### List 5 — the yellow-highlighted rows are KEPT

Two rows are highlighted yellow. The legend at the bottom of the sheet reads
**`Masih dalam proses persetujuan pencatatan di OJK`** — what is pending is the *pencatatan*, the
recording of a data change, **not the licence**. Both rows carry a full licence number and sit in
the main register above the `Cabut Izin` heading, so they stay in as `Regulated`.

The legend text itself was being emitted as two companies on each of the two sheets, because it
is written into the `Name` column. A lone populated cell is now treated as a heading **wherever it
sits**, including inside the Name column. That change also removed 5 footnote lines from list 1 —
lines like `*) PT Bank Harda Internasional Tbk berubah nama menjadi …` — which `name_problem()`
cannot catch because they are long, full of letters, and contain real bank names. **List 1's
fixture count is therefore 106, not the 111 this file previously claimed; the 5 extra were
footnotes.**

### List 11 — pdfplumber's phantom columns

`extract_tables()` returned the financing directory as a **21-column** grid, with the seven header
labels at columns 1, 4, 7, 10, 13, 16, 19 and the seven data fields at 0, 3, 6, 9, 12, 15, 18 —
consistently one column apart, so the header row never lined up with its own data and the list
parsed to **0 rows**. Columns are now folded together where no single row populates two of them,
which restores the seven real columns. **193 rows.**

### List 13 — a poster, not a table

The digital-asset register is published as a **designed poster**: 6 pages, 6 images per page,
zero ruling lines, and what tables `extract_tables()` finds are decoration. It parsed to 0 rows.
There is now a fallback that runs when generic table extraction yields nothing: `extract_words()`
clustered into lines, then split into two columns **only where the words actually leave a gutter
across the page middle**. Cutting on the mid-line itself destroys every centred line — pages 4–6
are laid out as a single centred column and lost all their entities that way. Entities are
recognised by their decree number, `S-14/D.07/2025 (1 Februari 2025)` /
`KEP-17/D.07/2026 (25 Mei 2026)`, with the preceding lines accumulated as the company name.

**32 entities, 0 duplicate decree numbers, 4 complete categories**: `Pedagang Aset Keuangan
Digital` 26, `Penyelenggara Bursa …` 2, `Lembaga Kliring Penjaminan dan Penyelesaian
Perdagangan …` 2, `Pengelola Tempat Penyimpanan …` 2.

### Header detection — a name column that is not called "Nama"

`Bank Kustodian.xlsx` and `Daftar Wali Amanat.xlsx` are the **same nine-column sheet** — Alamat,
Kota, Provinsi, Kode Pos, Telepon, Faksimili, E-mail — differing only in cell 0, which reads
`Bank Kustodian` on one and `Nama` on the other. No label rule can enumerate every entity type,
so the first was being discarded whole ("no header row, skipped"). When a row is otherwise
unmistakably a header (3+ recognised fields) but claims no `Name`, the first unclaimed label that
is not the row-number column is now taken as the name column. This can only rescue a sheet that
would have been thrown away entirely. **Bank Kustodian: 0 → 28 rows.**

---

## Field mapping

| Schema field | Source |
|---|---|
| `Name` | `Nama` / `NAMA BPR` / `NAMA BPRS` / the entity-type label, per file by header label |
| `Address_1` | `Alamat` / `ALAMAT BPR` |
| `Address_2` | `PROVINSI` where present |
| `City` | `KOTA/KABUPATEN` where present |
| `Zip` | `Kode Pos` where present; pinned to text |
| `Phone`, `Fax` | `No. Telepon` / `NO TELEPON`, `No. Fax`; list 2 splits one column into both |
| `Website`, `Email` | `Website`, `EMAIL` |
| `CoType` | per-list constant (table above); list 6 appends the folder path |
| `License_Type` | section header (list 1), folder path (list 6), or a type column when present |
| `InternalID_1` (+ `_type`) | `SANDI` (OJK bank code) where present |
| `InternalID_2` | licence / decree number (`STTD…`, `KEP-…/D.07/…`) where present |
| `RegulationDate` | licence/decree date column where present, else empty |
| `Cntry`, `RegCtry`, `RegCode` | `'ID'`, `'ID'`, `'OJK'` — constants |
| `RegulationType` | `'Regulated'`. Revoked entities are not emitted at all (list 5), so no `Withdrawn` value is used — **see NEEDS CONFIRMATION** |
| `ListCode`, `ListName`, `ListLabel` | per-list constants |
| `ListLanguage` | `'ID'` |
| `ListValidityDate` | the period parsed out of the source link or filename |
| `ListProcessDate` | `datetime.datetime.now().strftime('%Y-%m-%d')` |
| `Cntry - Mother company` | list 2 only — the country group header, mapped to ISO2 |

Columns are matched by **normalised header label, never by position**. Position-based indexing is
what broke v1 when OJK inserted a column. Sheet names are never hard-coded either — list 1's
sheet was `daftar` in 2023 and `Daftar Bank Umum` today; every sheet is read and the header row
found by label. That same mechanism rejects junk sheets (list 3's `Sheet1`/`Sheet2` province
lookups) without a sheet allow-list.

---

## Acceptance tests

### Offline suite — `OJK_SELFTEST=1 python ID_OJK_v2.py`

No network, so it runs anywhere. It drives every parser over fixtures in `tempfolder/fixtures/`
(13 archived landing pages, 2 article pages, 3 real OJK workbooks). **Verified 2026-09-03:
`SELFTEST: 58 passed, 0 failed`.**

| Group | Proves |
|---|---|
| schema | 43 keys in order; `add_row()` raises `KeyError` on an unknown key; one call appends to all 43 |
| period grammar | `Triwulan III 2025`→`2025-09-30`, `Triwulan II Tahun 2024`, `Desember 2025`, `Posisi 21 April 2026`, `Februari 2026`→`2026-02-28`; and that `Januari 2025` beats a `November 2024` sitting above it |
| discovery | lists 1/3/4 each yield exactly one `.xlsx` link; lists 5/7/8/9/11/12 each yield ≥10 dated articles with a correctly-parsed newest; list 6 yields exactly 5 top-level folders; both article fixtures yield download buttons (list 10's yields 3) |
| list-13 filter | keeps 8 of 10 links, dropping the *ITSK Terdaftar* series and the criteria PDF — **and that it is not a no-op** (10 unfiltered vs 8 filtered) |
| workbook parsing | list 1 → 106 rows, last row a bank and not a footnote, section→`License_Type`; list 3 → 1356 with `SANDI`→`InternalID_1`; list 4 → 173; list 3's junk sheets rejected by header detection |
| list-2 table | 22 rows; zero-width spaces stripped; all 22 map to a real ISO2 (13 distinct); 5 rows had a fax split out of `Telepon` |
| anti-vacuity | see below |

### The content assertions actually fire

An assertion that cannot fail is worse than none, so every content check is fed known-bad input
and must reject it:

- `name_problem()` fires on `''`, `'12'`, `'123456'`, `'4.000376e+10'`, `'12/03/2024'`, `'Yes'`,
  `'Nama'` — and passes `'PT BANK RAKYAT INDONESIA (PERSERO) Tbk'`.
- `qa_dataframe()` runs once on clean data (passes) and then on seven single-field mutations of
  it, and must raise on each: `Name='Yes'`, `Name='4.000376e+10'`, `Name='2024-01-01'`,
  `RegCode='WRONG'`, `ListLabel='9'`, `CoType=''`, and a mojibake `Name`.
- Excel round-trip: `'02710'` pinned to text survives; the **unpinned** integer `2710` comes back
  as `'2710'` and `digit_fingerprint()` detects it. *Measured:* a long all-digit ID
  (`40003764029`) **does** survive pandas → openpyxl → `read_excel(dtype=str)` on this machine, so
  scientific-notation loss is not the reproducible hazard here — leading-zero loss is, and the
  probe uses the failure mode that actually reproduces.

### Assertions in the production path

- **One shared file-validity test.** `file_kind(bytes)` checks magic bytes — `PK\x03\x04`,
  `\xd0\xcf\x11\xe0`, `%PDF`. The retry loop and the parse-time assert call the **same
  function**, so a WAF error page can never be retried as "nearly right" and then blamed on the
  parser. On final failure the bytes/HTML and landed URL are dumped to `tempfolder/`.
- **Schema funnel.** `add_row(**kw)` raises `KeyError` outside the 43 keys and asserts all 43
  columns stay the same length.
- **Content assertions on `Name`,** not just row counts: non-empty, not a bare integer, not a
  date, not `Yes`/`No`, not a section header echoed as an entity.
- **Excel round-trip** on write: ID/Zip/Phone/Fax/ListCode pinned to text, workbook read back,
  digit strings asserted intact.
- **Mojibake gate** before writing.
- **No list may silently emit zero rows** — that is an explicit `ListFailure`. The script exits
  **2** if any list failed but still writes the `.xlsx` for the lists that worked.
- **Per-list counts printed as ASCII only** — raw Indonesian text is never printed, because the
  production Windows console is cp1252.

---

## NEEDS CONFIRMATION FROM TICKET OWNER

1. **List 6 — natural persons.** 1380 of 1676 rows are individuals, not companies: the three
   `Profesi Penunjang Pasar Modal` professions (Konsultan Hukum 493, Notaris 407, Penilai 385)
   and `Ahli Syariah Pasar Modal` (95, file named *Orang Perseorangan*). The 2025-12-03 ruling
   excluded an individual register in a *different* folder but says nothing about these. Include
   or drop? Dropping leaves **296** rows.
2. **All 13 ListLabel values.** Not in the ticket. The arguable ones are list 8 (guarantee
   companies — `4` or `2`?) and list 10 (insurance brokers/adjusters — `2` or `4`?).
3. **List 5 revoked companies.** Currently *dropped entirely*. The alternative is to emit them
   with `RegulationType` = something other than `Regulated` plus a `CancellationDate` — the
   headings carry the year (`Cabut Izin Usaha Pada Tahun 2025`) but no exact date. Confirm which
   is wanted.
4. **List 2 home country.** Offices are in Jakarta so `Cntry = 'ID'`, and the country group
   header goes to `Cntry - Mother company`. Confirm, versus putting the home country in `Cntry`.
5. **List 13 series.** Confirm only *Perdagangan Aset Keuangan Digital* is wanted and the
   *ITSK Terdaftar* series on the same page is out of scope.

---

## Known limitations

- **Lists 8, 9 and 10 have never been run against the live site.** Their row counts, column
  layouts and sheet structures are unknown. They share Pattern C with four lists that do work.
- **The DrissionPage/Chromium fallback is unexercised.** `requests` handled everything on
  2026-09-03, including every postback, so the browser path has never actually run here.
- **Only the newest year is taken** from a year-filed folder (list 6, `Profesi Penunjang`). If a
  register is ever *split* across years rather than reissued, this would lose the older parts.
- **`License_Type` forward-fill.** Blank cells inherit the value above, because OJK commonly
  merges that column. Wrong for a source where a genuinely blank type follows a populated one.
- **List 11 `_section` cosmetic leak.** An address fragment
  (`Kebayoran Baru, Jakarta Selatan, 12190 JAKARTA`) leaks into the internal `_section` value for
  9 rows. `License_Type` is unaffected and the emitted columns are correct.
- **`ListValidityDate` for list 2 is empty** — the inline table carries no "data as of" date.
- **Section-header detection** treats any lone populated cell as a heading. A source that put a
  real single-field entity on its own row would lose it. Verified correct for lists 1 and 5.
- The fixtures and `tempfolder/httpcache/` are development aids, not output, and are not
  committed.
