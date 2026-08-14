# GB GFSC

## Regulator Information

- **Country/Region Code**: GB
- **Regulator Code**: GFSC
- **Full Name**: Guernsey Financial Services Commission
- **Website**: https://www.gfsc.gg/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6745

> The ticket has **no description** (`description: null`). The list inventory
> below was therefore taken from the **live site and from v1.6's own code**, as
> instructed.

## Script

- **Current Version**: `GB_GFSC_v1_7.py` (supersedes `GB GFSC_v_1_6.ipynb`;
  the sibling `GB GFSC_v_1_6.py` is a 0-byte file and is left untouched)
- **Approach**: two plain JSON endpoints + one detail page per entity for the
  address, fetched with an 8-worker thread pool. No browser at all.
  `verify=False` for the corporate TLS proxy.

### Why v1.7 exists

v1.6 could **never** have produced a complete file, and its list 3 was wrong by
definition.

**1. It crashed.** `total_pages = a_txt` ('14') was never `int()`-ed →
`TypeError: 'str' object cannot be interpreted as an integer`. And it ended with
`writer.save()`, removed in pandas 2.0
(`AttributeError: 'OpenpyxlWriter' object has no attribute 'save'`).

**2. Two debug breaks were still in the code:**

```python
if page == 2 : break        # -> only ever 3 pages of the grid
if i == 10   : break        # -> only ever 11 detail pages per list
```

At most 33 rows per list could reach `sqldict`.

**3. List 3 was a merge, not a subset — the headline finding.** The site's filter
panel is **additive, not exclusive**: default view 2545 rows; tick one
"(Revoked/Surrendered/Suspended)" box → 2547; tick all 11 → 3770. v1.6's third
pass ticked all 11 and wrote **every row it saw** as
`RegulationType='Formerly Regulated'` with `ListCode='2'`. So its "list 3" was
*the 2545 currently-regulated entities plus the 1225 revoked ones*, all
mislabelled and all colliding with list 2 on `ListCode`. Only the
`if i == 10: break` limiter hid this — remove it and 2545 rows are written wrong.

**4. Selenium removed entirely.** v1.6 drove Chrome, accepted the cookie banner,
clicked 11 filter checkboxes by **positional xpath**
(`.../div[2]/div/div[1]/label[8]/input`), then paged through DataTables one page
at a time. The grid is in fact a DataTables **client-side** table fed by two
plain JSON endpoints that return the whole dataset in one call:

```
https://www.gfsc.gg/gfsc-company/feed/registeredbusiness  ->  132 rows
https://www.gfsc.gg/gfsc-company/feed/regulated           -> 3770 rows
```

The 11 positional xpaths would silently tick the wrong box the moment GFSC
reorders the panel; they are gone.

**5. `City` was always the island.** v1.6 did
`City = Address.split(',')[-2]`, which on a Guernsey address
(`…, St Peter Port, Guernsey, GY1 2HJ`) returns **`Guernsey`**, never the town.

Other v1.7 changes: `ListName` filled (v1.6 never filled it), `ListLanguage`
`EN`, the feed's licence text → `License_Type` (commented out in v1.6),
`scriptfolder` per project convention (v1.6 hard-coded the retired
`OneDrive - moodys.com` tenant), and the non-schema `'Check'` column dropped.

### How lists 2 and 3 are split

One feed of 3770 rows is partitioned in a single pass on the entity's own filter
categories. A category counts as revoked when the token **ends** in a
parenthesis mentioning revoked / surrendered / suspended:

| category | revoked? |
|---|---|
| `Schemes (Revoked/Surrendered/Suspended)` | yes |
| `Lead/Joint Licensee (Surrendered prior to 1st November 2021)` | yes |
| `Closed Ended Scheme (Registered)` | no |

The trailing-parenthesis anchor is deliberate. **Three rows** carry a broken
`Filters` value where GFSC's own markup leaks into the category string:

```
Schemes (Revoked/Surrendered/Suspended)<span class="column-has-green-funds"></span>
```

DataTables matches the checkbox label against the **exact** category string, so
those three do *not* match the revoked filter and stay in the site's default
view. The anchored regex reproduces that, which is what makes the counts come
out at exactly the **2545 / 1225** a human counts on the site. A loose keyword
search instead yields 2542 / 1228. The three rows are printed at the end of every
run so the behaviour is visible rather than hidden.

### Robustness

The corporate TLS proxy intermittently answers **502 Bad Gateway** — a v1.7 run
died on exactly that while fetching the regulated feed. Every request now goes
through `get_with_retry()` (5 attempts, linear backoff). A detail page that still
cannot be read returns `None` rather than `''`, so "the proxy refused this page"
never masquerades as "this entity publishes no address"; the count is reported at
the end of the run with an explicit re-run warning.

## List Types

| ListNr | ListName | ListLabel | Source |
|--------|----------|-----------|--------|
| 1 | List of Registered Entities | *(blank)* | `gfsc-company/feed/registeredbusiness` |
| 2 | List of Regulated Entities | *(blank)* | `gfsc-company/feed/regulated`, current rows |
| 3 | List of Regulated Entities (Revoked/Surrendered/Suspended) | **4** | `gfsc-company/feed/regulated`, revoked rows |

Lists 1 and 2 are pre-existing, so `ListLabel` is left blank for colleagues to
fill manually (user decision, 2026-08-13). **List 3 is new**, so it does carry a
label: the register mixes banks, insurers, funds, fiduciaries and investment
licensees, so by the 1/2/3/4 rule it is **`4` (everything else)**.

Base: `https://www.gfsc.gg`

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | feed `name`, HTML stripped |
| InternalID_1 / _type | feed `GFSC_x0020_Ref` / `GFSC code` |
| License_Type | feed `Licences`, HTML stripped |
| Address_1 | detail page, `div#block-gfsc-theme-content .details-container .value[0]` |
| City | town below the island — see `split_gg_address()` |
| Zip | trailing postcode peeled off the address |
| Cntry / RegCtry / RegCode | `GB` / `GB` / `GFSC` |
| ListLanguage | `EN` |
| RegulationType | list 1 `Registered`, list 2 `Regulated`, list 3 `Formerly Regulated` |
| ListCode / ListName | per table above |
| ListProcessDate | run date (`%Y-%m-%d`) |

### `split_gg_address()`

`'Royal Bank Place, St Peter Port, Guernsey, GY1 2HJ'` → City `St Peter Port`,
Zip `GY1 2HJ`. The address is peeled from the right:

1. **Postcode** — Guernsey/Jersey/UK shapes, plus overseas ones (`75009` Paris,
   `D02 F3F2` Dublin, `DE 19808` Delaware) that would otherwise survive the peel
   and be written into `City`.
2. **Every trailing island / country token**, not just one — so
   `…, Jersey, Channel Islands` peels both.
   **Alderney and Sark are deliberately excluded** from that token list: they
   have no town below the island, so they must stand as the City themselves.
3. What remains is the town — **unless it is plainly a street line**
   (`28 Esplanade`, `2 Le Marchant Street`), in which case `City` is left
   **empty**. A street in the City column is worse than a blank one, because it
   looks like real data.

## Status / QA

- **Output**: `GB GFSC SQL Ready 2026-08-13 13.51.33.xlsx`, **3902 rows**, fixed
  43-column schema, sheet `SQL Ready`.

| ListNr | ListName | RegulationType | rows |
|--------|----------|----------------|------|
| 1 | List of Registered Entities | Registered | 132 |
| 2 | List of Regulated Entities | Regulated | 2545 |
| 3 | List of Regulated Entities (Revoked/Surrendered/Suspended) | Formerly Regulated | 1225 |
| | **Total** | | **3902** |

- All three counts match the site exactly: the page's own `.dataTables_info`
  reads "132 Records" and "2545 Records", and 3770 − 2545 = 1225. The script
  prints itself against that baseline on every run.
- `ListCode` values are `{1, 2, 3}` — **no collision**, which was v1.6's defect.
- Schema is an exact match for CLAUDE.md, no `Check` column;
  `RegulationType` and `ListProcessDate` non-empty on all 3902 rows.
- `Name`, `InternalID_1`, `License_Type`, `Cntry`, `ListName`, `ListLanguage`
  are 100% filled on all three lists.
- **Every detail page was read successfully** — zero proxy failures in the
  accepted run.
- Coverage per list (`Address_1` / `City` / `Zip`):

  | ListNr | rows | Address_1 | City | Zip |
  |---|---|---|---|---|
  | 1 | 132 | 132 | 132 | 131 |
  | 2 | 2545 | 2509 | 2499 | 2508 |
  | 3 | 1225 | 791 | 791 | 790 |

  The low list-3 figure is expected — a revoked entity often no longer publishes
  an address.
- **City parser check**: **0** of 3422 City values contain a digit
  (before the fix: 45 — 21 Paris rows reading `75009`, 9 reading `28 Esplanade`,
  and 15 other overseas postcodes). Top towns: St Peter Port 2989,
  St. Peter Port 240, St Sampson 38, Paris 21, London 19, St Helier 19,
  Alderney 14, St Martin 12.

### Known remaining artifacts

- **`St Peter Port` (2989) and `St. Peter Port` (240)** are both present. That
  punctuation variation is **as published by GFSC**; it is not normalised, so
  the output matches the source. Say the word if you want them folded together.
- **10 entities lose their `City`** because the address has no town between the
  street and the island (e.g. `Jtc House, 28 Esplanade, Jersey, JE2 3QA`).
  `Address_1` and `Zip` are still complete for those rows.

### Items needing your confirmation

1. **`Cntry` is `GB`**, following v1.6. Guernsey's own ISO 3166-1 alpha-2 code
   is **`GG`** (it is a Crown Dependency, not part of the UK). Tell me which one
   BVD expects — this affects all 3902 rows.
2. **List 3 `ListLabel = 4`.** New list, mixed population, so "everything else"
   under the 1/2/3/4 rule. Confirm.
3. **The 3 markup-mangled rows** (`EV Private Equity VI LP`,
   `NextEnergy Renewables Limited`, `Nobel Sustainability Fund LP, The`) are
   reported in **list 2**, because that is where the site itself shows them.
   They are arguably revoked. Confirm you want to keep matching the site.
4. **21 GFSC refs appear in both list 2 and list 3**, and 5 refs appear twice
   within list 3. These are **genuine**: the feed is one row per
   (entity, licence role), so the same ref can hold a live licence *and* a
   surrendered one — e.g. *Liberation Management Limited* is a current
   "Secondary Licensee, Pension Provider" and a former "Lead Licensee". Note
   also that a GFSC ref is **not a stable entity key**: ref `115887` carries
   *JTC Employer Solutions (Guernsey) Limited* in list 2 and *RBC cees Guernsey
   Limited* in list 3. Flagging in case downstream de-duplication assumes
   `InternalID_1` is unique.
5. **`RegulationType` values `Registered` / `Formerly Regulated`** — kept from
   v1.6's vocabulary. Confirm they are what BVD wants.

### Environment notes

- Global Python environment; `requests`, `beautifulsoup4`, `pandas`, `openpyxl`.
  No Selenium, no ChromeDriver.
- `verify=False` + `urllib3.disable_warnings` are required behind the corporate
  TLS proxy, which also needs the retry wrapper described above.
- Runtime ≈ 10 minutes, dominated by the 3902 detail pages at 8 workers.
