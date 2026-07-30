# US FED — Board of Governors of the Federal Reserve System

Jira: **DECD-6460** (parent epic DECD-3438 — Regulators 2026 — Crawlers)

Latest scraper: **`US_FED_v1.3.ipynb`**

## Lists

| ListCode | ListName | Source | ListLabel |
|---|---|---|---|
| 1 | Large Commercial Banks | https://www.federalreserve.gov/releases/lbr/current/default.htm | 1 |
| 3 | Foreign Banking Organization as a BHC | https://www.federalreserve.gov/releases/iba/ → most recent `YYYYMM/bycntry.htm` | 1 |

ListNr 2, 4 and 5 exist in older versions of the notebook but are **not** in the Jira scope and stay commented out / removed. ListNr 4 (FFIEC NPW download) was already marked non-operational because of a CAPTCHA.

## How it works

Both sources are **static, server-rendered HTML**. v1.3 drops Selenium/ChromeDriver entirely and uses `requests` + BeautifulSoup, which removes the ChromeDriver dependency and the `sleep(3)` waits.

`verify=False` is set on the session — required behind the corporate TLS proxy.

### List 1 — Large Commercial Banks
Single table, `class="pubtables"`. The bank name lives in `<th scope="row">` as `"BANK NAME / HOLDING CO NAME"`; the remaining 11 `<td>` carry rank, Bank ID, HQ, charter and asset figures.

- `Name` / `Name - Mother Company` ← the `th`, split on `" / "`
- `InternalID_1` ← Bank ID (`InternalID_1_type = 'Bank ID'`)
- `Address_1` ← Bank Headquarters (e.g. `COLUMBUS, OH`), `City` ← the part before the comma
- `Typology` ← Charter (`NAT`, `SMB`, `SNM`, …)
- `ListValidityDate` ← the "as of" date parsed off the page

### List 3 — Foreign Banking Organizations
Two hops: the `/releases/iba/` index is scanned for `YYYYMM/default.htm` links and the **highest** one wins, then `bycntry.htm` under that release is parsed. The page is 56 `<p class="ST4">` country headings paired 1:1 with 56 `<table border="1">`.

Entity names are published as `"NAME (CODE - DESCRIPTION)"`, e.g. `BANCO NACION ARGENTINA NY BR (USB - UNINSURED STATE BRANCH)`. v1.3 splits that suffix out:
- `Name` ← entity name without the suffix
- `CoType` ← the 2–4 letter code (`USB`, `UFB`, `REP`, `NAT`, …)
- `Typology` ← the expansion (`UNINSURED STATE BRANCH`, …)
- `Name - Mother Company` ← foreign parent, same suffix stripped
- `Cntry` / `Cntry - Mother company` ← ISO-2 from the country heading

## Maintenance notes / known breakage points

1. **LBR table selector.** v1.2 used `soup.find("table", {"cellspacing": "0"})`. That attribute is gone — the table is now `class="pubtables"`. If the parse returns `None` the notebook raises immediately rather than silently producing zero rows.
2. **LBR column shift.** The bank name moved from `tds[0]` into a `<th>`, so data rows now have **11** `<td>`, not 12. v1.2's mapping was off by one and would have put the national rank in `Name`.
3. **IBA release discovery.** v1.2 clicked an absolute XPath (`//*[@id="content"]/div[4]/…`) then `PARTIAL_LINK_TEXT "By Country"`. Both are brittle; v1.3 resolves the release directory by regex instead.
4. **ISO map.** `ARMENIA`, `DOMINICAN REPUBLIC` and `UNITED KINGDOM  (OTHER)` (note the **double space**, as published) were missing and produced `Cntry = None`. `UNITED KINGDOM` was mapped to the non-ISO code `UK`; corrected to `GB`. The loop now prints a `[WARN]` for any country not in the map instead of silently emitting a blank.
5. **`ExcelWriter.save()`** was removed in pandas ≥ 2.0 — v1.2 and earlier died on this line *after* a successful scrape. v1.3 uses `df.to_excel(path, sheet_name='SQL Ready', index=False)`.
6. **`sqldict`** in v1.2 carried an extra `'Check'` key, which violates the fixed schema in `CLAUDE.md`. Removed in v1.3.

## Last run

2026-07-29 — **4169 rows**: ListCode 1 = 3798, ListCode 3 = 371.
LBR release March 31 2026; IBA release 202603. All 55 distinct `Cntry` codes resolved, no blanks, no encoding flags.
