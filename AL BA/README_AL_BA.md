# AL BA — Bank of Albania (Banka e Shqipërisë)

Jira: **DECD-6828** — the ticket is titled only "AL BA" and **has no description**: no list
table, no ListNames, no ListLabels, no scope decisions. Everything below marked
*(assumed)* was derived from the site itself and needs the ticket owner's sign-off — see
**NEEDS CONFIRMATION FROM TICKET OWNER** at the bottom.

- Script: `AL_BA_v2.py` (production, Python 3.8 compatible)
- Notebook: `AL_BA_v2.ipynb` (same code, cells split on the `#---- Begin_XXX ----` markers)
- Output: `AL BA SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx`, written into this folder
- Reference only, superseded: `Al_BA_v1.py` (Selenium + tabula; see *What was wrong with v1*)

Root: `https://www.bankofalbania.org`

---

## Lists

Six supervised registers, all under `/Supervision/Licensed_institutions/`. Each landing page
carries a `ul.block-list` of downloads: a *licensed* file, a *revoked* file, and — on lists 5
and 6 only — an *agents* file. Every list is emitted with the **same ListCode for licensed and
revoked rows**; the two are distinguished by `RegulationType`.

| ListCode | ListName *(assumed — taken from the page's own `<h1>`)* | ListLabel | CoType | source format | ListLanguage |
|---|---|---|---|---|---|
| 1 | List of Licensed Banks | 1 | Bank | inline HTML + `ajxDt.php` AJAX cards | EN |
| 2 | List of Licensed Foreign Exchange Bureaus | 4 | Foreign Exchange Bureau | PDF (108 pages) | SQ |
| 3 | List of Licensed Non-bank Financial Institutions | 4 | Non-bank Financial Institution | XLSX (index sheet + one card sheet per entity) | EN |
| 4 | List of Licensed Savings and Loan Associations and their Unions | 4 | Savings and Loan Association / Union of Savings and Loan Associations | PDF (5 pages) | SQ |
| 5 | List of Licensed Payment Institutions | 4 | Payment Institution | XLSX | EN |
| 6 | List of Licensed Electronic Money Institutions | 4 | Electronic Money Institution | XLSX | EN |

`ListLanguage` is per list, not per row: it records the language of the **document that was
actually parsed**. Lists 2 and 4 publish only Albanian documents (list 4's English landing page
serves an *older* document — see *Site quirks*), so those rows are `SQ`. The other four are `EN`.

### ListLabel justification

Repo rule: **1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.**

- List 1 → **1**. Commercial banks, unambiguous.
- Lists 2, 3, 5, 6 → **4**. FX bureaus, non-bank financial institutions, payment institutions
  and e-money institutions are none of bank/insurance.
- List 4 → **4** *(judgment call, genuinely arguable)*. Savings & Loan Associations (*shoqëri
  kursim-krediti*) are deposit-taking credit co-operatives supervised under the banking law.
  They are not licensed as banks, so `4` was chosen — but a reasonable reviewer could argue `1`.
  **This one needs confirmation.**

The Bank of Albania does not supervise insurance at all (that is AL AFSA), so `2` and `3`
cannot occur here.

---

## How it works

### 1. Every download link is resolved at runtime

There is **no hard-coded filename and no hard-coded document id anywhere in the script.** For
each list the scraper fetches the landing page, reads `ul.block-list`, keeps every anchor whose
href ends in `.pdf` / `.xlsx` / `.xls`, and classifies each one by its **link text**:

```python
def classify(link_text):
    f = fold(link_text).lower()
    if 'revok' in f or 'shfuqizuar' in f or 'revoked' in f or 'revocation' in f: return 'revoked'
    if 'agjent' in f or 'agent' in f: return 'agents'
    return 'licensed'
```

The Bank of Albania rebuilds these documents in place and the ids change (list 4's SQ page
already serves `34487` where the EN page still serves `29856`), so anything hard-coded rots.
This is a known recurring failure mode in this repo, and it is the reason the classification
keys off text rather than position: `li[1]` is exactly the bug v1 shipped.

Every list page is tried in **English first, Albanian as runtime fallback** (`LISTS` carries
both paths). English is preferred because the English link text is what makes
licensed/revoked/agents classification robust.

### 2. Three parsers, one row funnel

| parser | used by | approach |
|---|---|---|
| `parse_banks_html` | list 1 licensed | reads `div.fq-list`; each block's `h4` is the name, its inner `a[data-url]` points at an `ajxDt.php` fragment that is fetched with plain `requests` and mapped **label → value** from the `<tr>`s plus the address `<p>` |
| `parse_xlsx` | lists 3, 5, 6 | sheet 0 is an index (rows whose first cell matches `^\d+(\.\d+)?$`) and is the **authoritative name source**; sheets 1..N are one detail card per entity, paired positionally with the index; fields are located by **label text**, never by cell coordinates |
| `parse_pdf` | list 2, list 4, and every revoked file | sequence-following record walker: a line is a new record when it starts `N.` and `N == expected`, with a section-restart rule for documents that renumber from 1 |

All three feed a single `add_row(**kw)` funnel:

```python
def add_row(**kw):
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        v = kw.get(k, '')
        sqldict[k].append('' if v is None else str(v))
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(sorted(lens)))
```

so a typo'd or invented column raises instead of silently producing a ragged frame — which is
what let v1's illegal 44th key survive.

### 3. `fold()` — diacritic folding for matching only

Albanian `ë` and `ç` are everywhere and they defeated every ASCII label regex during
development (a whole `Licencë nr. 4, datë 01.07.2002` line was being swallowed into an entity
name). `fold()` maps `ë→e`, `ç→c`, strips combining marks via NFKD, and normalises curly quotes,
en/em dashes and NBSP:

```python
def fold(s):
    ...
```

**Every label test runs against the folded copy; every value that reaches `sqldict` keeps the
original characters.** 1100 of 1190 names carry `ë`/`ç` in the delivered workbook, unmodified.

### 4. Section restart in the PDFs (a real, silent data loss)

The Savings & Loan licensed PDF has two sections that each restart numbering at `1`:
`UNIONET E SHOQËRIVE…` (1 union) then `SHOQËRITË E KURSIM–KREDITIT` (15 associations). A strict
`n == expect` walker yields **15** records, drops the union, and *looks perfectly plausible*.
The fix is an explicit restart rule:

```python
if n == expect:
    start = True; expect += 1
elif n == 1 and blocks and HDR_RE.match(prev):
    start = True; expect = 2
```

→ **16** records. Any future list that gains a second section is handled by the same rule.

---

## Field mapping

| sqldict column | source |
|---|---|
| `Name` | HTML `h4` / XLSX index cell / PDF text after `N.`, including wrapped continuation lines. Keeps the source's trailing district (`…SH.P.K., DURRËS`). |
| `EntryType` | constant `Head Office` — every register lists head offices; branch counts appear as text, not as rows |
| `CoType` | per list, from the table above (list 4 splits Union vs Association by PDF section) |
| `Typology` | the Albanian sector term (`Banka`, `Zyra e Kembimit Valutor`, …) |
| `InternalID_1` / `_type` | NUIS (a.k.a. NUIS/NIPT, "unique registration number"); `InternalID_1_type` is standardised to the single string **`NUIS`** across all six lists even though the sources spell it three ways |
| `Address_1` | address label (`Adresa:` / `Address:` / the HTML address `<p>`). For FX bureaus the head-office address is trimmed out of the multi-office `Zyra 1: … Zyra 2: …` blob |
| `City` | district resolved from the address / name tail against a whitelist of Albanian cities |
| `Phone`, `Fax`, `Email`, `Website` | label-matched (`Tel`, `Tel/Fax`, `E-mail`, `www`) |
| `License_Type` | the licence/authorisation sentence as published (100% filled) |
| `RegulationType` | `Regulated` for licensed files, `Revoked` for revoked files |
| `RegulationDate` | licence date (`datë dd.mm.yyyy`) → ISO |
| `CancellationDate` | revocation date from the revoked files → ISO |
| `Name - Mother Company` + `Cntry - Mother company` | **v2 addition**: first shareholder above 5% where the source publishes one |
| `Cntry` | `AL` · `RegCtry` `AL` · `RegCode` `BA` |
| `ListValidityDate` | **scrape date** — no source document carries a publication or "as of" date (grep-verified across all 17 downloaded files) |
| `ListProcessDate` | scrape date, `now.strftime('%Y-%m-%d')` |
| `bvdid`, `priority`, `Zip`, `InternalID_2/3`, `LEI Code`, `BIC SWIFT Code`, mother-company address fields | intentionally empty — not published |

### Observed fill rates (run of 2026-08-25, 1190 rows)

`Name` 100% · `License_Type` 100% · `RegulationType` 100% · `RegulationDate` 1189/1190 ·
`City` 98% · `Address_1` 55% · `Phone` 55% · `CancellationDate` 45% (= 536 of 539 revoked) ·
`InternalID_1` 5% · `Email` 5% · `Fax` 4% · `Name - Mother Company` 4% · `Website` 3%.

The low ID/contact coverage is the source, not the parser: the revoked files (539 rows, 45% of
the output) publish little more than name + revocation decision, and the FX-bureau PDF publishes
no NUIS at all. NUIS is effectively a lists-1/3/5/6 field.

---

## Row-count reconciliation (run of 2026-08-25)

| list | source | licensed | revoked | total |
|---|---|---|---|---|
| 1 | inline HTML + `ajxDt.php` | 13 | 7 | 20 |
| 2 | PDF, 108 pages | 586 | 353 | 939 |
| 3 | XLSX | 22 | 19 | 41 |
| 4 | PDF, 5 pages | 16 | 158 | 174 |
| 5 | XLSX | 4 | 1 | 5 |
| 6 | XLSX | 10 | 1 | 11 |
| **TOTAL** | | **651** | **539** | **1190** |

Independently checked, not just counted:

- all 36 XLSX index↔card pairings were verified entity by entity;
- list 4's SQ and EN PDFs were diffed and contain the identical 15+1 record set;
- list 1's 13 licensed banks match the 13 accordion blocks on the live page.

---

## Acceptance tests (all run in-process, every run, before and after the write)

Content, not just shape — a previous regulator in this repo reconciled 997/997 rows with a
`Name` column full of `Yes`/`No`, so counting is not enough:

1. `list(df.columns) == SCHEMA_KEYS` and `len(df.columns) == 43`; `'Check' not in df.columns`.
2. `Name` is non-empty, ≥3 chars, not a bare number, not a date, and **never a field label**
   (`^(NUIS|Tel|Fax|www|e-?mail|Adres|Licen)\b` is rejected) — this is what catches a parser
   that has drifted one line off.
3. **Mojibake gate** — no `Name` contains `U+FFFD` or the `Ã` / `â€` double-decode signatures.
   Observed: `0 of 1190 Names garbled; 1100 Names still carry Albanian ë/ç`.
4. `RegulationType ∈ {Regulated, Revoked}` on every row; `ListProcessDate` stamped on every row.
5. `RegCtry == 'AL'`, `RegCode == 'BA'`, `Cntry == 'AL'`, `InternalID_1_type ∈ {'', 'NUIS'}`.
6. **Excel round-trip** — the workbook is written with ID/Zip/Phone/Fax/ListCode pinned to text,
   then **read back** with `dtype=str` and asserted: same row count, same column order, no
   float-coerced ids (`4.0003e+10`), identical id multiset, no post-write mojibake, and the
   same 1100 diacritic-bearing names. Observed: `Round-trip OK: 1190 rows x 43 cols; 63 NUIS
   values intact, sample 'J91725007P'`.
7. `ast.parse(..., feature_version=(3,8))` — verified OK for both the `.py` and the notebook's
   concatenated source.

Nothing is `print()`ed from the scraped text itself. A `ascii_only()` helper folds and
`?`-substitutes anything non-ASCII before it reaches stdout, because the Windows production
console is cp1252 and `ë` raises `UnicodeEncodeError` there.

---

## What was wrong with v1

`Al_BA_v1.py` is kept for reference only. Defects fixed in v2:

1. **Illegal 44th sqldict key.** v1 ended its dict with `'Phone - Mother company': [], 'Check': []`.
   The schema is exactly 43 keys. Removed, and now enforced by `add_row` + an explicit assert.
2. **Selenium.** Removed entirely. v2 is plain `requests` + `BeautifulSoup`; no browser is
   needed anywhere, including for the list-1 accordion.
3. **tabula.** Removed — it needs a JVM that the control server does not have. PDFs are read
   with `pdfplumber`.
4. **Revoked entities were never actually emitted.** v1 had a `RegulationType = 'Revoked'` code
   path, but it clicked `//*[@id="middleColumn"]/div[2]/ul/li[1]` — the **first** link only,
   which is always the licensed file. The revoked branch was dead code. v2 emits 539 revoked
   rows. *(Note for the ticket owner: any prior delivery from v1 contained licensed rows only.)*
5. **Dead list-1 selector.** v1 did `h4.find_parent('div')` → `.find('p')` → `.find('tbody')`
   and read fields by position (`tr_s[1]` = NUIS, `tr_s[2]` = Phone). That markup no longer
   exists; the fields now live behind an `ajxDt.php` AJAX fragment. v2 discovers it from
   `data-url` and maps by label.
6. **Section-restart data loss** in the Savings & Loan PDF (15 vs 16) — described above.
7. **No list metadata at all.** v1 populated no `ListName`, `ListLabel`, `ListLanguage`,
   `ListValidityDate` or `EntryType`. All are populated in v2.
8. Two smaller source-quirk fixes found while testing: a wrapped ALL-CAPS union name was being
   truncated by the section-header regex, and the source typo `"Addres s:"` (Tirana Bank) lost
   an address.

---

## Site quirks that will break this scraper later

- **Document ids rotate.** Everything is resolved from the landing page at runtime; if a page
  drops its `ul.block-list`, `discover()` returns nothing and that list logs a WARN rather than
  silently emitting zero rows.
- **List 4's English page is stale.** The EN landing page serves document `29856` while the
  Albanian page serves `34487`. Both were diffed and carry the same records today, but the EN
  page is clearly not being maintained — hence `ListLanguage = SQ` for that list.
- **PDF numbering with no space.** The FX-bureau PDF writes `10.ZYRA E KËMBIMEVE…` with no space
  after the period. A naive `^(\d+)\.\s` caught 496 of 586 records. The separator must stay
  optional.
- **The FX-bureau register is a 108-page PDF** and is by far the slowest part of the run.
- **`ajxDt.php` is an internal endpoint.** If the bank moves list 1 to a normal detail page,
  `parse_banks_html` needs re-pointing (the `h4` names would still be recovered).
- **Agent registers** on lists 5 and 6 are labelled *"në proces përditësimi"* (being updated) by
  the bank itself and may change shape without notice.

---

## NEEDS CONFIRMATION FROM TICKET OWNER

DECD-6828 has no description, so all ten of these are **my decisions, not the ticket's**:

1. **ListNames.** All six were taken from each page's own `<h1>`. If the ticket expects specific
   wording, it needs to be supplied.
2. **ListLabels.** Assigned 1 / 4 / 4 / 4 / 4 / 4. **List 4 (Savings & Loan Associations and
   their Unions) is genuinely ambiguous between 4 and 1** — deposit-taking credit co-operatives
   supervised under the banking law. Please confirm all six.
3. **Revoked entities are IN.** 539 of the 1190 rows are `RegulationType = 'Revoked'` with a
   `CancellationDate`. Flagged loudly because **v1 never emitted a single revoked row** (see
   defect 4), so this is a large, visible change in the delivered row count — from ~651 to 1190.
   Set `INCLUDE_REVOKED = False` at the top of the script if they should be excluded.
4. **Agent registers on lists 5 and 6 are OUT** (`INCLUDE_AGENTS = False`, matching v1's
   effective behaviour). The bank marks them as being updated. Flip the flag if agents are wanted
   — they would need their own `EntryType`/`CoType` decision first.
5. **`ListValidityDate` = the scrape date.** No source document carries a publication or "as of"
   date; I grepped all 17 downloaded files. If a different convention applies, say which.
6. **`InternalID_1_type` = `'NUIS'`** everywhere. The sources spell it `NUIS`, `NUIS/NIPT` and
   "Unique registration number (NUIS/NIPT)"; one value was chosen for consistency.
7. **Licensed and revoked rows of a list share one `ListCode`**, separated only by
   `RegulationType`. If revoked entities should carry their own ListCodes/ListNames, that is a
   one-line change.
8. **`Name` keeps the source's trailing district** (`ZYRA E KËMBIMEVE VALUTORE "A.M.A." SH.P.K.,
   DURRËS`). `City` is populated separately, so the district is duplicated. Confirm whether the
   name should be trimmed.
9. **`Name - Mother Company` is a v2 addition** (49 rows) taking only the *first* shareholder
   above 5%. Confirm whether it is wanted at all, and whether "first only" is the right rule.
10. **`ListLanguage`** is set per list to the language of the document actually parsed (SQ for
    lists 2 and 4, EN for the rest) rather than a single value for the whole delivery.

---

## Not verified

- The scraper has **not** been executed on the Windows control server, only on macOS. Python 3.8
  compatibility was proven by `ast.parse(feature_version=(3,8))`, which is a syntax check, not a
  runtime check. `pdfplumber`, `openpyxl`, `bs4` and `requests` are all present on that box for
  other regulators, but this specific script has not run there.
- **3 revoked rows have no parseable `CancellationDate`** (2 on list 2, 1 on list 4). The source
  gives only a year in prose, e.g. *"Revokuar licenca në vitin 2015"*. Left empty rather than
  guessed at a day/month.
- **2 licensed entities have a genuinely empty NUIS** in the source — `Tirana Bank S.A.` (list 1)
  and `ALBANIAN FINANCIAL INSTITUTION SH.P.K.` (list 3). Checked against the live pages; not a
  parser defect.
- The 25 rows with an empty `City` are entries whose address/name carries no recognisable
  Albanian district; they were not force-filled.

---

## Run record

- 2026-08-25 — `AL_BA_v2.py` run end to end on macOS: **1190 rows × 43 columns**, licensed 651 /
  revoked 539. `py3.8 ast.parse OK`. Mojibake 0/1190. Round-trip OK, 63 NUIS values intact.
- 2026-08-25 — `AL_BA_v2.ipynb` executed end to end via `nbclient`: identical output
  (1190 rows, same per-list split, same assertions passing).
