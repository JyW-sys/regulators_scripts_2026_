# IQ CBIRA — Central Bank of Iraq

Jira: [DECD-5026](https://moodysdatapipeline.atlassian.net/browse/DECD-5026) (parent epic DECD-3438)

## Source

`https://cbi.iq` — bilingual (Arabic default). The **English** version is served only after a
session **language cookie** is set by visiting the toggle URL once:

```
https://cbi.iq/language/change/english/https:----cbi.iq--page--93
```

(Note: `https://cbi.iq/en/page/..` returns a "Blocked" page — the cookie is the only way.)
Every list is a plain server-rendered HTML `<table>`, so the scraper uses `requests` (with that
cookie) + BeautifulSoup. No Selenium, no JS, no OCR.

## Lists & pages

| ListCode | ListName | Page(s) |
|---|---|---|
| 1 | Banks (6 subsections → `Typology`) | 23 Government · 24 Local commercial · 113 Local Islamic · 126 Branches of local banks abroad · 114 Branches of foreign banks · 118 Foreign rep. offices |
| 2 | Non-banking Financial Institutions | 25 (4 tables → sub-category as `Typology`) |
| 3 | International economic and financial institutions | 22 (headerless name list) |
| 4 | Authorized electronic collection/payment institutions | 94 (3 tables → sub-category as `Typology`) |

### Parsing rules

- **Entity row = first cell is a number** (the `No.` column). This single rule skips title rows,
  repeated header rows, and **rowspan continuation rows** (e.g. p94 lists multiple "responsible
  persons" per company on extra rows with no company name — those are not new entities).
- Columns are mapped by **header keyword** (`classify()`), tolerant of the per-table header
  variations (`Bank name`/`Institution Name`/`Company Name`, `Bank and telephone address`/`Branch
  address and phone`, `Number and Date of Certification`/`License number and date`, …).
- Phones are embedded inside the address cell for List 1 → extracted into `Phone`; List 4 has a
  dedicated `Phone Number` column.
- `E-mail & Website` cell split into `Email` (has `@`) and `Website` (domain/`www`).
- Certification/License cell → the `dd/mm/yyyy` is captured into `RegulationDate`.
- **List 3** (p22) has no header — each row's first cell is taken as the entity name (AMF, BIS,
  World Bank, IMF, Union of Arab Banks, Islamic Development Bank, Paris Club).

## Output

`tempfolder/IQ CBIRA SQL Ready <timestamp>.xlsx`, sheet **"SQL Ready"**, standard `sqldict` schema.

- `RegCtry`=IQ, `RegCode`=CBIRA, `ListLanguage`=English, `RegulationType`=**Regulated**.
- `Cntry`=IQ for lists 1/2/4; **blank for List 3** (those are international bodies, not Iraqi).
- `Typology` carries the subsection/sub-category; `RegulationDate` from certification dates;
  `License_Type` for List 4 where present. `ListProcessDate`=run date.

## Run

```
python "IQ CBIRA/IQ CBIRA_v1.py"
```

## Last run (2026-06-10) — 147 entities

| ListCode | rows | | ListCode | rows |
|---|---|---|---|---|
| 1 Banks (8+24+31+6+16+2) | 87 | | 3 International institutions | 7 |
| 2 Non-banking FIs | 26 | | 4 E-collection/payment | 27 |

Per-page counts cross-checked against the number of numbered rows in each live table
(incl. p114=16 and p94=27 after skipping continuation rows). Name 100%, 0 duplicates.
