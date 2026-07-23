# GM CBG — Central Bank of The Gambia

Jira: [DECD-5023](https://moodysdatapipeline.atlassian.net/browse/DECD-5023) (parent epic DECD-3438)

## Source

Central Bank of The Gambia registers at `https://www.cbg.gm`. Each list is a **static
Bootstrap HTML table** (`table table-striped`), server-rendered with no JavaScript, no
pagination and no anti-bot — so the scraper uses plain **`requests` + BeautifulSoup**
(no Selenium). Extraction is **header-driven** (`classify()`), with per-cell parsing because
the Name/Address/Contact cells are multi-line.

Cell shapes:
- **Name** cell embeds `Manager: <person>` / `Status: Active` lines below the entity name —
  the entity name is the **first line** (`first_line()`); the rest is dropped.
- **Address** cell is `street\ncity` → `Address_1` = all but last line, `City` = last line.
- **Contact Details** cell mixes phone + website link → `parse_contact()` pulls the `<a href>`
  as Website (mailto → Email) and the remaining text as Phone.

## Lists (ListCode = Jira ListNr)

| ListCode | ListName | URL | Notes |
|---|---|---|---|
| 1 | Commercial Banks | /list-of-licensed-banks | |
| 2 | Insurance Companies | /insurers | |
| 3 | Forex Bureaux | /list-of-approved-bureaus | |
| 4 | Finance Companies | /list-of-licensed-microfinance-institutions | **first** table only (`Finance Company`); the 2nd table (`VISACA`) is excluded per Jira |
| 5 | Mobile Money Operators | /mobile-money | different 5-col layout (Company, Managing Director, Address, Contact No., Website) |

## Output

`tempfolder/GM CBG SQL Ready <timestamp>.xlsx`, sheet **"SQL Ready"**, standard `sqldict` schema.

- `RegCtry`=GM, `RegCode`=CBG, `Cntry`=GM, `ListLanguage`=English.
- `RegulationType`=**Regulated** (every entity on these licensed/approved lists shows `Status: Active`).
- `ListProcessDate`=run date (`%Y-%m-%d`).

## Run

```
python "GM CBG/GM CBG_v1.py"
```

## Last run (2026-06-10) — 121 entities

| ListCode | ListName | rows |
|---|---|---|
| 1 | Commercial Banks | 11 |
| 2 | Insurance Companies | 21 |
| 3 | Forex Bureaux | 80 |
| 4 | Finance Companies | 7 |
| 5 | Mobile Money Operators | 2 |

Field fill: Name 100% (no Manager/Status leakage). Address 87%, City 36%, Phone 66%,
Website 11%, Email 0% — sparse fields mirror the source (many insurance/forex rows have blank
contact cells; the site exposes no email addresses). No encoding issues, no in-list duplicates.
