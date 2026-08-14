# JP FSAJP — Financial Services Agency of Japan

## Regulator Information

| | |
|---|---|
| **Country** | Japan (`JP`) |
| **Regulator** | Financial Services Agency (金融庁) |
| **RegCode** | `FSAJP` |
| **Jira** | [DECD-6758](https://moodysdatapipeline.atlassian.net/browse/DECD-6758) |
| **Index page** | <https://www.fsa.go.jp/en/regulated/licensed/index.html> |
| **Lists** | 12 (ListNr 1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13, 14) |
| **Current version** | `JP_FSAJP_v2.py` |
| **Previous version** | `JP_FSAJP_v1.ipynb` (kept as history — do not run) |

The ticket notes *"same url for all the lists, just select the correct file to
scrape"*: every list is an Excel workbook linked from the one index page above.

## Script / Approach

`JP_FSAJP_v2.py` is a plain `requests` script — no browser.

1. Fetch the index page and collect every `<li>` that contains an `.xls`/`.xlsx`
   anchor.
2. Match each of the 12 ticket list names against those `<li>` labels by Jaccard
   token overlap and take the best link. Anything scoring below `MIN_MATCH`
   (0.35) raises instead of scraping the wrong file — the worst genuine match
   measured is 0.50 (*Credit Associations* → `s_banks.xlsx`).
3. `GET` each workbook and read it from memory with `pd.ExcelFile(io.BytesIO(...))`.
4. Parse every sheet with one generic, label-driven parser (below).
5. Write all rows into the 43-column `sqldict` and save to the regulator folder.

### The generic parser

The 12 workbooks have their header on row 1, 2, 3, 4 or 5, with a title, an
"as of" date and sometimes a total above it. Rather than hard-code those
offsets, `find_header()` scans the first 15 rows for the first row that names a
**Name** column *plus* at least one of **JCN / Address / Telephone**. Fields are
then addressed by label, so a column added or reordered upstream no longer
shifts the output.

Rows below the header are dropped when they are:

- **blank** in the name column;
- a **repeated header block** — `s_banks.xlsx` carries two ("Federation of
  Credit Associations", then "Credit Associations");
- a **section label or footnote** — a name cell with every other cell in the row
  empty (e.g. `keito.xlsx`'s closing footnote).

`Country/Area`, `Nationality` and `Business category` are **merged cells**: the
value appears once against the first entity of a group and the rest are blank,
so each is carried down. The `Business category` column also holds running
annotations (`Total 4 banks`) which are neither kept nor allowed to end a group.

### Self-check

Ten of the sheets state their own count ("Total 35 banks", "15 companies",
"companies:41"). The script parses that number and compares it with the rows it
produced, printing `[OK]` when all agree and listing any disagreement at the end.
This is the QA baseline — if the FSA changes a layout, the count mismatch says so
rather than the run silently shrinking.

## Why v2 exists

`JP_FSAJP_v1.ipynb` no longer completes. Verified by running it on 2026-08-13
(only the hard-coded `scriptfolder` was patched so it could start):

```
[Start New Reg] -- Working with list JP FSAJP 1 --
[INFO] -- Maybe the file link is error, Change to xlsx --
FileNotFoundError: [Errno 2] No such file or directory:
  '.../JP FSAJP/tempfolder/.com.google.Chrome.Uxk3B5'
```

It dies on the **first** list. Two defects combine:

1. **Four of the twelve hard-coded URLs are dead.** The FSA migrated them from
   `.xls` to `.xlsx`. Measured live:

   | URL in v1 | status |
   |---|---|
   | `city.xls` | **404** |
   | `s_banks.xls` | **404** |
   | `ins_life.xls` | **404** |
   | `ins_holding.xls` | **404** |
   | the other 8 `.xlsx` | 200 |

2. **The `.xlsx` fallback is not awaited.** v1 reacts to the 404 with
   `driver.get(regdict[reg] + 'x')` — which does build the right URL — and then
   immediately calls `os.listdir(tempfolder)`. Chrome is still writing, so the
   listing returns its in-progress temp file (`.com.google.Chrome.Uxk3B5`), whose
   name matches neither of the `.tmp` / `.crdownload` guards above it. `pd.ExcelFile`
   then opens a file that Chrome renames away underneath it.

Fixing only the four URLs would leave the download race in place. v2 removes the
race entirely by dropping Selenium — all 12 workbooks are static files that
answer an ordinary `GET` — and resolves the links from the index page so the next
rename does not break it again.

Also fixed in v2:

| | v1 | v2 |
|---|---|---|
| Header detection | "first row with no NaN" + fixed slices (`data.columns[2:-5]`) | by column label |
| List 9 mother company | wrote the **telephone** column (both read `columns[3]` after the slice) | the affiliation column, by label |
| `Typology`, `ListLanguage`, `ListLabel` | never filled | filled |
| `License_Type` | the 5 business-category flag columns were sliced away | joined from the marked columns (list 8) |
| `CoType` | not captured | from `Business category`, carried through merged cells |
| `Zip` | last space-token if the address starts with a digit — missed every address beginning with a building name, and any with trailing spaces | postal-code regex |
| `City` | not captured | address tail, or `Prefecture` where the sheet has one |
| JCN placeholders | `-`, `―`, `－` written through as IDs | folded to empty |
| `scriptfolder` | hard-coded `C:\Users\wuj1\OneDrive - Moody's\...` | `__file__` with a `getcwd()` fallback |
| Save | `writer.save()` — removed in pandas 2.x | `df.to_excel(...)` |
| Schema | extra non-schema `Check` column | exactly the 43 CLAUDE.md columns |

## List Types

`ListLabel` per the CLAUDE.md rule (1 = bank, 2 = insurance, 3 = both, 4 = other).

| ListNr | ListName | ListLabel | Workbook | Rows |
|---|---|---|---|---|
| 1 | City Banks and Trust Banks | 1 | `city.xlsx` | 92 |
| 2 | Regional Banks | 1 | `reg.xlsx` | 96 |
| 3 | Bank Holding Companies | 1 | `bank_holding.xlsx` | 31 |
| 4 | Credit Associations | 1 | `s_banks.xlsx` | 255 |
| 5 | Keito Financial Institutions | 1 | `keito.xlsx` | 1 |
| 6 | Financial Institutions engaged in Trust Business | 1 | `fietb.xlsx` | 61 |
| 8 | Financial Instruments Business Operators | 4 | `fibo.xlsx` | 1954 |
| 9 | Financial Instruments Intermediary Service Providers | 4 | `fiisp.xlsx` | 681 |
| 11 | Life Insurance Companies | 2 | `ins_life.xlsx` | 41 |
| 12 | Non-Life Insurance Companies | 2 | `ins_nonlife.xlsx` | 57 |
| 13 | Insurance Holding Companies | 2 | `ins_holding.xlsx` | 15 |
| 14 | Trust Companies | 4 | `trustcompanies.xlsx` | 37 |
| | | | **Total** | **3321** |

Four workbooks carry a second sheet, folded into the parent list (as v1 did):

- **List 1** — `City Banks and Trust Banks` (35) + `Foreign Banks` (57) = 92
- **List 2** — `Regional Banks` (61) + `Regional Banks II` (34) + `Others` (1) = 96
- **List 12** — `domestic companies` (35) + `Branch Offices` (22) = 57

**List 5 really is one row.** `keito.xlsx` lists only The Norinchukin Bank; its
footnote states the other 31 credit federations of agricultural cooperatives and
8 of fishermen's cooperatives sit under the regional finance bureaus and are not
enumerated on this sheet.

## Field Mapping

| Source column | sqldict field |
|---|---|
| `name` / `name(English)` / `Name of company` / `The name of a …` | `Name` |
| `JCN` | `InternalID_1` (+ `InternalID_1_type` = `JCN`) |
| `Registration numbers` | `InternalID_2` (+ `InternalID_2_type` = `Registration Number`) |
| `Business category` | `CoType` |
| Type I / Type II / Investment Advisory / Investment Management / Securities-Related (marked with ○) | `License_Type`, `/`-joined |
| `Address` | `Address_1` (postal code and city split out) |
| `Postal Code`, else parsed from `Address` | `Zip` |
| `Prefecture`, else the address tail | `City` |
| `Country/Area` / `Nationality` | `Cntry` |
| `Telephone` / `phone` / `Phone(main)` | `Phone` |
| `Affiliation financial instruments firm` | `Name - Mother Company` |
| — | `RegCtry` = `JP`, `RegCode` = `FSAJP`, `ListLanguage` = `EN`, `RegulationType` = `Regulated` |
| — | `ListCode` = ListNr, `ListName` = `Typology` = the list name, `ListProcessDate` = run date |

`name(Japanese)` (list 2) is read but not written — `Name` takes the English form.
`Jurisdiction` (lists 8/9, the supervising finance bureau) has no schema column and
is not written.

## Status / QA

**Runs green.** Last verified run 2026-08-13 →
`JP FSAJP SQL Ready 2026-08-13 18.17.53.xlsx`, **3321 rows × 43 columns**.

- Every sheet that declares its own total agrees with the rows parsed —
  35 / 57 / 61 / 34 / 1 / 31 / 41 / 35 / 22 / 15 all matched (`[OK]` printed).
- Columns are exactly the 43 in CLAUDE.md, in order; no `Check` column.
- `Name`, `RegulationType`, `ListProcessDate`, `Typology`, `ListName`, `ListLabel`,
  `ListLanguage`, `RegCtry`, `RegCode`, `ListCode` — 0 empty on all 3321 rows.
- `RegulationType` is `Regulated` throughout; `ListProcessDate` is all `2026-08-13`.
- `InternalID_1` 96.5% filled and **every** value is exactly 13 digits.
- `Zip` is filled on 100% of rows whose source address carries a postal code
  (92/92, 37/37, 31/31, 1/1; 60/61 for list 6). Lists 2, 4, 11, 12, 13 have **no**
  address column at all upstream, and the `fibo`/`fiisp` addresses genuinely omit
  the postal code — those blanks are the source, not the parser.
- `License_Type` filled on 1954/1954 list-8 rows.
- `Name - Mother Company` filled on 681/681 list-9 rows, and now holds the
  affiliation, not the phone number.
- 0 duplicate `Name` + `ListCode` pairs.

**Not verified from here:** this was run on the dev Mac. It has not been run on
the Windows production box.

## Items needing confirmation

1. **`ListLabel`** — set here as 1 for the six bank lists, 2 for the three
   insurance lists, and 4 for lists 8, 9 and 14 (financial instruments business
   operators, intermediary service providers, trust companies). v1 left the
   column empty. Confirm the three `4`s.
2. **`Cntry`** — v2 follows v1: the `Country/Area` (list 1 *Foreign Banks*) and
   `Nationality` (list 12 *Branch Offices*) columns go to `Cntry`, so 79 rows
   carry a **home country** while the other 3242 are blank even though every
   entity is addressed in Japan. The alternative is `Cntry = 'JP'` everywhere.
   Kept as-is to avoid changing what downstream already receives — say if you
   want it flipped.
3. **Second sheets** — lists 1, 2 and 12 fold their extra sheets (`Foreign
   Banks`, `Regional Banks II` / `Others`, `Branch Offices`) into the parent
   list, as v1 did. If any should be a list of its own, they need their own
   ListNr.
4. **List 5** — one row is correct for the sheet, but confirm the 39 federations
   named only in its footnote are genuinely out of scope.

## Environment notes

- Written for **Python 3.8** on the Windows production box: no f-strings, no
  walrus, no dict `|=`, and the source is pure ASCII.
- `verify=False` + `urllib3.disable_warnings` for the corporate TLS proxy.
- No browser and no `tempfolder` — workbooks are held in memory.
- Output `.xlsx` is gitignored and must not be committed.
