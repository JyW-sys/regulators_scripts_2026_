# BE BNBE — Nationale Bank van België / Banque nationale de Belgique

Jira: **DECD-6465** (parent epic DECD-3438 — Regulators 2026 — Crawlers)

Latest scraper: **`BE BNBE_v5.ipynb`**

## Lists

25 lists, all scraped from the **French** (`/fr/`) tree of `www.nbb.be`.

The **Site total** column is the figure the NBB itself prints on the page
(`Nombre total d'établissements`). v5 checks every list against it on every run and refuses
to write the workbook if any list disagrees — see *Count audit* below.

| ListCode | ListName | ListLabel | Site total | Rows |
|---|---|---|---|---|
| 1 | List of financial institutions in order of identification | 1 | n/a (workbook) | 103 |
| 2 | Credit Institutions Authorised in Belgium | 1 | 46 | 46 |
| 3 | EEA credit institutions with a branch in Belgium | 1 | 46 | 46 |
| 4 | EEA credit institutions — freedom to provide services | 1 | 607 | 607 |
| 5 | Representative offices of EEA credit institutions | 1 | 14 | 14 |
| 6 | Licensed insurance companies | 2 | 52 | 52 |
| 7 | Branches in Belgium of EEA insurance undertakings | 2 | 43 | 43 |
| 8 | EEA insurance undertakings — freedom to provide services | 2 | 777 | 777 |
| 9 | Reinsurance undertakings | 2 | 30 | 30 |
| 11 | Stockbroking firms under Belgian law | 4 | 9 | 9 |
| 12 | Branches of EEA stockbroking firms | 4 | 8 | 8 |
| 13 | Payment institutions under Belgian law | 4 | 31 | 31 |
| 14 | EEA payment institutions with a branch in Belgium | 4 | 10 | 10 |
| 15 | EEA payment institutions — freedom to provide services | 4 | 419 | 419 |
| 16 | Electronic money institutions authorised in Belgium | 4 | 3 | 3 |
| 17 | EEA e-money institutions with a branch in Belgium | 4 | 2 | 2 |
| 18 | EEA e-money institutions — freedom to provide services | 4 | 268 | 268 |
| 20 | US reinsurers operating without a Belgian establishment | 2 | 11 | 11 |
| 21 | Insurers with full / systematic reinsurance conventions | 2 | 11 | 11 ⚠ |
| 22 | Central securities depositories authorised in Belgium | 4 | 2 | 2 |
| 23 | Institutions holding dematerialised securities accounts for third parties | 4 | 26 | 26 |
| 24 | Account keepers for dematerialised securities (Companies Code) | 4 | 37 | 37 |
| 25 | Limited-network payment service providers | 4 | 12 | 12 |
| 26 | Account-aggregator payment institutions | 4 | 3 | 3 |
| 27 | Mutual guarantee companies | 4 | 4 | 4 |

The Jira table has no ListNr 10 and no ListNr 19, and its list-8 row carries no number.
That is the ticket's own numbering — v5 mirrors it rather than renumbering.

## How it works

Selenium + BeautifulSoup. Two source shapes:

- **ListCode 1** — a downloadable workbook, reached by clicking the download link on the
  *codes d'identification des banques* page.
- **ListCodes 2–27** — server-rendered HTML tables on the NBB prudential-supervision pages.

Every `/supervision-financiere/controle-prudentiel/...` URL now 302s to the newer
`/activites/supervision-financiere-et-resolution/...` tree. The old URLs still work and are
kept as-is; both land on the same page.

## Count audit (v5)

Each list page publishes its own row count. v5 scrapes that number, compares it against both
the parsed count and the count that actually reaches the workbook, prints the table, and
**raises before writing** if anything disagrees:

```
 ListCode  stated  parsed  emitted   ok
        2      46      46       46 True
        4     607     607      607 True
        8     777     777      777 True
       18     268     268      268 True
```

List 2 prints one total per sub-section (10 of them); they are summed. Set
`AUDIT_STRICT = False` in the writer cell to inspect a mismatching run instead of aborting.

This exists because the defect below shipped silently and had to be caught by hand.

## The v4 defect: a de-duplication that destroyed real records

v4's writer cell ran:

```python
df = df.drop_duplicates(subset=["Name", "ListCode"], keep='first')
```

**The parser was never wrong.** Every list parsed to exactly the NBB's published total. The
loss happened afterwards, in that one line: entities that merely *share a name* were treated
as duplicates and dropped.

| List | Site | v4 shipped | Lost |
|---|---|---|---|
| 2 | 46 | 44 | `Euroclear SA` and `Argenta BVG` each appear twice — once *approuvée*, once *désignée* |
| 4 | 607 | 604 | e.g. `DZ Privatbank AG`, `Banco Santander, S.A.` |
| 8 | 777 | 774 | `ERGO Versicherung AG`, `HDI Versicherung AG`, `USAA S.A.` |
| 18 | 268 | 267 | `Decta Limited` |

These are genuine separate registrations — the same undertaking notified from two different
member states, or a holding company that is both *approved* and *designated*. Both rows
belong in the output.

**Do not reinstate a name-based `drop_duplicates` in the writer.** If exact-duplicate rows
ever need removing, do it per list, on a key that includes the identifier — and let the count
audit prove it removed only what you intended.

## ListCode 1 — one row per institution

The source workbook `full_list_current.xlsx` is an *identification-code register*: 1000
numbered slots, **780** of them carrying a name, but only **103 distinct institutions** —
one bank holds many code ranges.

v5 emits **one row per institution** (103), keyed on the first available language name, and
puts that institution's first identification code in `InternalID_1`
(`InternalID_1_type = 'Identification Number'`). v4 discarded the identification number
entirely, which for a code register was the one field worth keeping.

Two counts you may arrive at independently, and why they differ:

- **96** — distinct values in the Dutch name column alone. Too low: 7 institutions have no
  Dutch name at all (French/English only) and would be dropped entirely.
- **104** — what v4 reported. Too high: v4 keyed de-duplication on the *joined*
  `Dutch | French | German | English` name, so a single institution split in two whenever one
  of its codes carried a Dutch-only name and another carried Dutch + French.

> An earlier revision of this file asserted that "104 is the correct output, verified against
> the raw workbook". That was wrong — 104 was an artifact of the joined-name key, not a count
> of institutions.

**Consequence:** a bank with several identification codes keeps only its first. If the
downstream consumer needs every code, this list has to be emitted one row per code (780
rows) instead. That is a scope decision, not a bug — the current behaviour was chosen
deliberately for this ticket.

### The Jira URL for list 1 is dead

DECD-6465 gives `https://www.nbb.be/doc/be/be/protocol/current_codes.xls`. That returns
**HTTP 404** — the NBB renamed the file. v5 uses the live replacement,
`full_list_current.xlsx`, which is what the download link on the landing page now points to.
This is a deliberate deviation from the ticket text. **The ticket should be corrected.**

## ⚠ ListCode 21 duplicates ListCode 20 — by instruction

DECD-6465's URL cell for list 21 is **identical to list 20's**
(`.../entreprises-dassurance-ou-de-28`). v5 follows the ticket literally, so lists 20 and 21
now contain **the same 11 US reinsurers**.

The two Jira cells for list 21 contradict each other:

| Jira cell | Value | Points at |
|---|---|---|
| ListName | *"Entreprises d'assurance inscrites ayant conclu une convention comportant la réassurance intégrale et systématique…"* | `.../entreprises-dassurance-ou-de-2` — a live page with **22** entities, titled word-for-word that ListName |
| URL | `.../entreprises-dassurance-ou-de-28` | the list-20 page, **11** US reinsurers |

v4 used `-ou-de-2` (22 rows, content matching the ListName). v5 uses `-ou-de-28` as the
ticket specifies. The ListName is kept verbatim from Jira, so **ListCode 21's ListName no
longer describes its contents**.

**This needs a decision from the ticket owner.** If the URL cell was a copy-paste slip, change
list 21's URL back to `.../entreprises-dassurance-ou-de-2` and it returns to 22 rows. Note
that `-de-2` is also a `<table>`-shaped page vs `-de-28`'s `<ul>` shape — v5 routes list 21
through the tbody branch, so reverting the URL also means moving `'BE BNBE 21'` back into the
`<ul>` branch in the main loop.

## Known gaps — NOT fixed in v5

These are outside the defects reported for this round. Flagged, not silently fixed.

1. **`Cntry` is hardcoded `'BE'` on every row.** Correct for the Belgian-law lists, wrong for
   the passporting lists. ListCode 4 is German banks in Frankfurt, Wiesbaden and Hamburg —
   all currently stamped `BE`. The home member state *is* on the page
   (`Etat membre du siège social : Allemagne`) and drives the per-country grouping, so it is
   recoverable. Affects lists 4, 7, 8, 12, 14, 15, 17, 18, 20, 21.
2. **`City` / `Zip` parsing is positional and misfires on multi-word cities.**
   `Taunusanlage 8, 60329 Frankfurt Am Main` yields `City = "Main"`. `City` is 66 % filled,
   `Zip` 51 %.
3. **Never populated:** `Phone`, `Website`, `Email`, `Address_2`, `License_Type`,
   `RegulationDate`, `Name - Mother Company` — all 0 %.
4. **`RegulationType` is `'Regulated'` for every row.** Cell 4 defines a richer per-list map
   (`Licensed` / `Registered` / `EEA Authorised`) that is built and then never used.

## Maintenance notes / historical breakage

1. **Download-link selector (the v3 breakage).** v3 used
   `driver.find_element(By.LINK_TEXT, "Full list of current codes")`. The anchor gained a
   child `<div class="file-icon__extension">xlsx</div>`, so its rendered text is now `''` and
   **both** `LINK_TEXT` and `PARTIAL_LINK_TEXT` raise `NoSuchElementException`. v4/v5 match on
   the href instead: `a[href$='full_list_current.xlsx']`.
2. **Hardcoded Windows `scriptfolder`.** v3 pinned `C:\Users\wuj1\OneDrive - Moody's\...`.
   v4/v5 use the `try: __file__ / except NameError: os.getcwd()` idiom from `CLAUDE.md`.
3. **`ExcelWriter.save()`** was removed in pandas ≥ 2.0 — v3 scraped successfully and then died
   on the write. v4/v5 use `df.to_excel(path, sheet_name='SQL Ready', index=False)`.
4. **Non-schema `'Check'` key.** v3's `sqldict` carried an extra column, violating the frozen
   43-column schema in `CLAUDE.md`. Removed.
5. **`ListLabel` was never populated** (0 % in v3). Assigned from a `ListCode → ListLabel` map;
   raises if a new ListCode appears without one.
6. **`ListLanguage`** was never populated. All 25 source URLs are on the `/fr/` tree → `FR`.
7. **A stale v3 write cell silently clobbered the output sheet.** A trailing
   `df.to_excel(filename, index=False)` ran *after* the corrected write and rewrote the
   workbook with pandas' default sheet name `Sheet1`, at a relative path. Neutralised in v4.
   **If you add a cell below the writer, make sure it does not write.**

## Last run

2026-07-29 — **2574 rows**, 43 columns, single sheet `SQL Ready`, all 25 ListCodes present.
Count audit passed on all 24 HTML lists. `ListLabel` 100 % filled (1 = 816, 2 = 924,
4 = 834), `ListLanguage` 100 % `FR`, `Name` / `RegulationType` / `ListProcessDate` 100 %
filled, no blank names, no encoding flags.

File: `BE BNBE data 2026-07-29 15.19.00.xlsx` (the folder's existing `data` naming
convention, not `SQL Ready` — matches the 2025-11-07 file).

For reference, the 2025-11-07 baseline covered only lists 2–18 — it has **no ListCode 1 and
no lists 20–27**, so those are new in this ticket and have no historical count to compare
against.
