# EG FRAEG

## Regulator Information

- **Country/Region Code**: EG
- **Regulator Code**: FRAEG
- **Full Name**: Financial Regulatory Authority (الهيئة العامة للرقابة المالية)
- **Website**: https://fra.gov.eg/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6365

## Script

- **Current Version**: `EG_FRAEG_v2.py`
- **Approach**: plain `requests` with a desktop User-Agent and `verify=False`.
  `fra.gov.eg` previously rejected every programmatic request from the office
  network; from the current (VPN-switched) network it answers **HTTP 200** for
  the register pages and both PDFs, so **no DrissionPage / Selenium is needed**.
  HTML parsed with BeautifulSoup, PDFs with `pdfplumber`.
- **Output**: `EG FRAEG SQL Ready <timestamp>.xlsx`, sheet `SQL Ready`,
  **272 rows** — 47 + 30 + 195.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Egyptian Insurance Companies | https://fra.gov.eg/en/سجلات-في-مجال-التأمين/?taxonomy_filter=company_records_1_1_3_3&filtered_type=insurance-and-reinsurance-companies | Extract the entities from the table (Company name in column 2 and address in column 4), translate from Arabic to English and add to the column Name in our template Excel file. The Arabic versions can be copied to the Mother Company columns. |
| 2 | Foreign Reinsurance Brokers | https://fra.gov.eg/wp-content/uploads/2026/06/FRA-Foreign-Reinsurance-Brokers-Non-Resident-List-June-2026-1.pdf | NEW LIST! Extract the entities from the pdf. |
| 3 | FRA Reinsurance Companies | https://fra.gov.eg/wp-content/uploads/2026/06/FRA-Reinsurance-companies-Its-Branches-List-June-2026-1.pdf | NEW LIST! Extract the entities from the pdf. |

`ListLabel = 2` (insurance) for all three lists.

## Row counts

| ListCode | Source | Rows | How verified |
|---|---|---:|---|
| 1 | HTML grid, 3 pages (20 + 20 + 7) | **47** | pagination walked until an empty page; page counts printed per page |
| 2 | 1-page PDF table | **30** | header row located by text, `Reg. No.` 1–30 |
| 3 | 10-page PDF, two numbered tables | **195** | 151 reinsurance companies (serials 1–151) + 44 reinsurers' branches (serials 1–44); serial continuity asserted — no gaps, no duplicates |

The script re-asserts these counts at the end of every run (`EXPECTED`) and fails
loudly if the source structure changes.

## ListNr 1 — page structure & parsing

The register is a paginated WordPress grid with 5 columns
(`No. | Company | Chairman of Board | Headquarters Address | Insurance Type`).
Column headings are English but the **cell content is Arabic**. Pagination is
`…/page/N/?taxonomy_filter=…&filtered_type=…`; the walk stops on the first page
that yields no `<td>` rows.

Every grid row links to a `/en/company_records/<slug>/` detail page whose tables
publish considerably more than the grid does. Those fields are harvested and
mapped as follows:

| Detail label (AR) | Meaning | SQL-Ready column |
|---|---|---|
| `اسم الشركة` / `اسم المكتب` | company / representative-office name | `Name` (translated), `Name - Mother Company` (Arabic) |
| `اسم الشركة بالانجليزية` | FRA's own English name (8 records) | `Name` — wins over the translation |
| `العنوان` | address | `Address_1` (translated), `Address_1 - Mother company` (Arabic) |
| `رقم الشركة` / `رقم المكتب` | company / office number | `InternalID_1` (+ `_type`) |
| `رقم الترخيص` / `قرار الهيئة بالترخيص` | licence no. / licensing decision no. | `InternalID_2` (+ `_type`) |
| `تاريخ الترخيص` / `تاريخ القرار` | licence date / decision date | `RegulationDate` |
| `تليفون`, `فاكس` | phone, fax | `Phone`, `Fax` |
| `الموقع الالكتروني`, `البريد الالكتروني` | website, e-mail | `Website`, `Email` |
| `اسم النشاط` | licensed activity | `License_Type` |

Fill rate: `Name` 47/47, `Address_1` 47/47, `City` 47/47, `InternalID_1` 47/47,
`RegulationDate` 47/47, `Phone` 45/47, `Fax` 27/47, `Website` 21/47,
`Email` 17/47.

### Translation (Arabic → English)

Per the Jira comment, `Name` and `Address_1` are English and the Arabic
originals are copied to `Name - Mother Company` / `Address_1 - Mother company`.
Three sources are used, in priority order:

1. **FRA's own English name** (`اسم الشركة بالانجليزية`) where the register
   publishes one — 8 records (Misr Insurance, Misr Life Insurance,
   SCI – Suez Canal Insurance, Mohandes Insurance co, each appearing twice).
   These are copied verbatim, including FRA's own casing.
2. **A curated `NAME_EN_OVERRIDE` map** covering all 47 current entities.
   Machine translation gets brand names wrong — it returns *Saatchi* for
   **SACE S.p.A.**, *Arup* for **Orope**, *CAF* for **KAF**, and mangles
   *MAPFRE Asistencia Compania Internacional*. Spellings were cross-checked
   against the registrant's own website / e-mail domain published by FRA
   (`oropeegypt.com`, `kaf.com.eg`, `iskanins.com`) and against the represented
   parent named on the detail page (`MAPFRE ASISTENCIA COMPANIA INTERNACIONAL
   DE SEGUROS Y REASEGUROS SOCIEDAD ANONIMA`, `SACE S.P.A`).
3. **Google machine translation** (`deep_translator`) for addresses, and as the
   fallback for any company FRA adds to the register after this build — so a new
   entity never lands in the file with an Arabic `Name`.

MT results are cached in `tempfolder/translation_cache.json`, so re-runs are
byte-stable and work offline once primed.

Two transliterations could not be confirmed against an external source and are
best-effort — flagged here rather than silently shipped:

- ListNr 1 row 2 — `شركة فريمير ليمتد لخدمات التامين واعادة التامين`
  (a Cypriot company) → **"Fremier Insurance and Reinsurance Services
  Representative Office"**.
- ListNr 1 row 42 — `الوفاء لتأمينات الحياة_مصر` → **"Al Wafaa Life Insurance
  – Egypt"**.

`آروب` is rendered **Orope** (not the Lebanese group's *Arope* spelling) because
FRA's own record for both Egyptian entities links to `www.oropeegypt.com` and
`orope.egypt@orope.com.eg`.

### Known source quirks (ListNr 1)

- **FRA lists 4 companies twice.** Misr Insurance, Misr Life Insurance, Suez
  Canal Insurance and Mohandes Insurance appear as grid rows 6–9 (Arabic record)
  **and** rows 44–47 (English record). Both are kept — the output row count must
  match the source. They are not deduplicated.
- **Dots stored as the digit `0`** in several websites and e-mails
  (`www.sci-egypt0com`, `misrins3@tedata0net0eg`). A literal `0` in front of a
  TLD is not a valid host, so `fix_contact()` repairs it
  (→ `www.sci-egypt.com`, `misrins3@tedata.net.eg`).
- **Dangling separators on phone numbers** (`-7605445-`) are stripped; a genuine
  pair such as `24517620-24517622` is left intact.
- The grid appends `الممثل القانوني : <person>` (legal representative) to the 5
  representative-office names — stripped, it is not part of the entity name.
- `City` is derived from the translated address: an explicitly named governorate
  wins (Cairo / Giza / Alexandria / …), otherwise the Cairo-or-Giza district is
  mapped (Mohandiseen, Dokki, Agouza, Smart Village → Giza; Zamalek, Maadi,
  Heliopolis, Nasr City, Fifth Settlement, New Cairo, Qasr El Nil → Cairo).
  Result: 23 Cairo / 24 Giza.
- The detail pages of the 5 representative offices also publish the **represented
  parent company** (`اسم الشركة \ الهيئة التي يمثلها المكتب`, e.g. *Marsh &
  McLennan Ltd*, *MAPFRE Asistencia*, *SACE S.p.A.*) and its foreign address.
  Those are **not** written to the Mother Company columns because the Jira
  comment reserves those columns for the Arabic original of the entity's own
  name/address. Say the word if the parent data should go somewhere instead.

## ListNr 2 — page structure & parsing

Single-page text PDF, one clean ruled table, 7 columns:
`Reg. No. | Company Name | Country | Regulatory Authority | Address | Director |
Authorization Date`. The header row is located by its text (not by index) and
asserted, then every row whose first cell is a number is taken → 30 rows.

- `Reg. No.` → `InternalID_1` (`FRA Registration Number`).
- `Country` → `Cntry` via an explicit ISO-3166 alpha-2 map (`pycountry` is not
  installed on this machine); an unmapped country is reported at the end of the
  run rather than silently blanked.
- `Authorization Date` (`DD/MM/YYYY`) → `RegulationDate` as `YYYY-MM-DD`.
- `License_Type` = `Foreign Reinsurance Broker (Non-Resident)`.
- `Regulatory Authority` and `Director` have no home in the fixed schema and are
  not captured. `City` is not published as its own field — it stays inside
  `Address_1`.

## ListNr 3 — page structure & parsing

The one PDF the Jira row points at holds **two** numbered tables:

| Pages | Table | Rows | `EntryType` | `License_Type` |
|---|---|---:|---|---|
| 1–8 | FRA Reinsurance Companies List 2026 | 151 | *(blank)* | `Reinsurance Company` |
| 9–10 | FRA Reinsurers' Branches List 2026 | 44 | `Branch` | `Reinsurer's Branch` |

Both are emitted under `ListCode 3`.

**Why coordinate parsing and not `extract_table()`:** the `COUNTRY` cell is a
*merged* cell spanning a whole country block (e.g. one `France` cell covering
12 reinsurers), so `extract_table()` collapses the block into a single row with
all 12 names joined by newlines and drops the serials. Instead the parser:

1. reads the vertical rules to get column boundaries
   (`SER. | COUNTRY | COUNTRY Rate | REINSURER | …ratings`);
2. reads the **full-width** horizontal rules to get the country-group
   boundaries (in-group rules only span the `SER.` column);
3. clusters words into visual lines with a 4pt tolerance — the serial digit and
   its company name are not always on exactly the same `top`, which is what
   made a naive line split lose ~10 rows;
4. broadcasts the merged country / country-rating over every reinsurer in the
   group;
5. keeps only lines whose `SER.` cell is a number, which drops the running page
   header and the two footnotes.

Serial continuity (1–151 and 1–44, no gaps, no duplicates) is asserted — the
strongest available check that nothing was dropped or double-counted.

The rating columns (S&P / A.M. Best / Fitch / Moody's financial and credit
ratings, and the sovereign `COUNTRY Rate`) have no home in the fixed schema and
are not captured.

**`SER.` is deliberately NOT written to `InternalID_1`** — it is a positional
line number that shifts whenever FRA republishes the list, not a registry
identifier. (ListNr 2's `Reg. No.` *is* labelled a registration number by FRA
and is kept.)

### Footnotes not emitted as rows

Page 8 carries two notes naming further entities allowed to write reinsurance
business in Egypt. They sit **outside** the numbered table and are not emitted,
so that the row count matches the published lists:

- **NOTE I** — Lloyd's; Arab War Risks Insurance Syndicate (AWRIS).
- **NOTE II** — Assuranceforeningen Skuld (Gjensidig), Norway; Gard Marine &
  Energy Insurance (Europe) AS, Norway; NorthStandard Limited, UK.

Say the word if these 5 should be added as rows.

## Field conventions

- `RegulationType` = `Regulated` for every row (all three lists are registers of
  authorised entities).
- `ListProcessDate` = run date (`%Y-%m-%d`).
- `ListValidityDate` = `2026-06-24` for ListNr 2 and 3 (both PDFs are stamped
  *"Update 24 June 2026"*); blank for ListNr 1, which is a live page.
- `ListLanguage` = `AR` for ListNr 1 (Arabic source), `EN` for ListNr 2 and 3.
- `RegCtry` / `RegCode` = `EG` / `FRAEG`; `ListCode` = the Jira ListNr.
- `Cntry` = `EG` for ListNr 1; the entity's own ISO-2 country for ListNr 2 and 3
  (they are foreign brokers / reinsurers admitted to the Egyptian market).

## Environment notes

- Runs on the global Python (macOS). Requires `requests`, `beautifulsoup4`,
  `pandas`, `pdfplumber`, `deep_translator`, `openpyxl`.
- `verify=False` + `urllib3` warning suppression is required behind the
  corporate TLS proxy.
- Downloaded PDFs and the translation cache live in `tempfolder/`; the
  `.xlsx` is written to the regulator folder itself, per project convention.

### Running on the control server (Windows, Python 3.8)

**Copy `tempfolder/translation_cache.json` across with the script.**
`translate_text()` consults the cache before it touches a provider, and the
shipped cache covers every Arabic string the current site content produces, so
a normal run imports no translation library at all and works offline.

The provider is only reached for text FRA has added or changed since this build.
`googletrans` is used first — the same library as every other translating
scraper here (`YE CBYE`, `SD CBOS`, `LB BLI`, `CN CSRC`) — with
`deep_translator` as a fallback. The 3.x API is synchronous and the 4.x API is
asyncio; the script detects which one is installed with
`inspect.iscoroutinefunction(Translator.translate)` rather than reading the
version string, because **the 4.0.2 distribution still reports
`googletrans.__version__ == '3.4.0'`**.

`deep_translator` is *not* required and is awkward to install on Python 3.8
(current releases need 3.9+; `deep-translator==1.11.4` is the last 3.8-compatible
version). If a provider genuinely has to be installed, the in-repo pattern is
`ensure_pip_package()` from `GB FCAUK/GB_FCAUK_FFAEXT_v2_July16_2026.ipynb`.

**v2 fixed a crash specific to that machine**: the Windows console is cp1252,
which cannot encode Arabic. The v1 translation warning printed the Arabic source,
so `UnicodeEncodeError` was raised *from inside the exception handler* and killed
the run instead of falling back to the Arabic original as designed. v2 forces
stdout to UTF-8 and keeps source text out of that message.
