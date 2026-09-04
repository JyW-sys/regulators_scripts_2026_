# BD IDRABD — Insurance Development and Regulatory Authority (Bangladesh)

Jira: **DECD-6974**  ·  RegCtry `BD`  ·  RegCode `IDRABD`

Production scraper: **`BD_IDRABD_v2.py`**  ·  Notebook: **`BD_IDRABD_v2.ipynb`**

> **STATUS: run end-to-end against the live site on 2026-09-02 from the development Mac.**
> 108 rows, all five lists matched the site's own row counts, QA passed, Excel round-trip
> verified. Both the `.py` and the `.ipynb` were executed; they produce identical output.
> Everything below that is *not* directly observed is labelled as such.

---

## Why there is a v2: v1 is completely dead

`BD_IDRABD_v1.ipynb` cannot work any more, and not because of a selector tweak. IDRA rebuilt
`idra.org.bd` as a **Nuxt 3 SPA**. Three independent breakages, all measured:

1. **All five v1 URLs return HTTP 404.** Verified by fetching each one. No redirect is issued —
   the old `/site/page/<uuid>/-` route no longer exists.
2. **The new public pages contain zero `<table>` tags.** A plain GET returns HTTP 200 and
   ~256 KB of HTML, but the table is client-rendered. v1's `soup.find_all('table')[0]` would
   raise `IndexError`.
3. **v1's cell addressing is gone.** It selected cells by inline CSS width —
   `tbody.find_all('td', style=re.compile(r'width:\s*180px'))` for list 1, `246px` for list 2,
   `145px`/`78px`/`102px`/`97px` for list 4. The new CMS emits no such styles.

**Decision: patch forward, do not rebuild from `Template/`.** The *list definitions* did not
change at all — same five lists, same five names, nothing added or removed. Only the transport
and the cell addressing had to be replaced, and the house structure (`regdict` / `sqldict` /
`Begin_*` sections) still fits. Starting from the template would have thrown away a correct
list inventory to regain nothing.

Two additional defects in v1 that are fixed in v2, independent of the site change:

- **v1's `sqldict` had 44 keys** — it appended a non-schema `'Check'` key. v2 uses the fixed 43.
- **v1's final cell could never run**: it called `writer.save()` (removed in modern pandas) and
  `driver.quit()` on a `driver` that is never defined anywhere in the notebook.

### regdict diff — v1 (existing) vs DECD-6974 (required)

| ListNr | ListName | v1 URL | Jira URL | Verdict |
|---|---|---|---|---|
| 1 | List of Life Insurers | `/pages/static-pages/6922e04a933eb65569e265aa` | `/page/লাইফ-বীমাকারী-প্রতিষ্ঠানসমূহ-5` | **URL changed** (v1's is a half-migrated API id; returns 404 JSON) |
| 2 | List of Non-Life Insurers | `/site/page/450e34d8-…/-` | `/page/নন-লাইফ-বীমাকারী-7` | **URL changed** (404) |
| 3 | List of Life Bancassurance Institutions | `/site/page/6dba4800-…/-` | `/page/লাইফ-46` | **URL changed** (404) |
| 4 | List of Non-Life Bancassurance Institutions | `/site/page/c25211d9-…/-` | `/page/নন-লাইফ-19` | **URL changed** (404) |
| 5 | List of Authorized Insurtech Institutions | `/site/page/37e6fd51-…/-` | `/page/ইন্স্যুরটেক-প্রতিষ্ঠানসমূহের-তালিকা` | **URL changed** (404) |

- ListNrs **added: none**. **Removed: none**. ListNames: **identical on all five**.
- The diff is *purely* a transport change — but a total one: 5 of 5 URLs.

---

## The one thing to know: it is a POST, not a GET

Every list is served by a single JSON endpoint:

```
POST https://idra.org.bd/idra-cms/api/v1/portal/getElement/<slug>
```

`<slug>` is the **last path segment of the public page URL**, percent-encoded exactly as it
appears in the browser address bar (the slugs are Bengali). The scraper derives it with
`page_url.rstrip('/').split('/')[-1]`, so the Jira URLs remain the only hard-coded input.

**A GET on this endpoint returns HTTP 401.** That 401 is misleading — it is not an auth wall.
The endpoint needs **no token, no cookie, no API key, no browser**; it just has to be a POST.
Chasing the 401 as an authentication problem is the single easiest way to waste a day here.

The response carries the entire table twice, as raw HTML:

| field | content |
|---|---|
| `body` | Bengali rendering |
| `body_en` | English rendering |

So English comes free with the same request — there is no locale cookie, header or query
parameter to find. `POST …/portal/getLanguageType` does confirm two locales (`en`, `bn`), but
the translation is stored per page as a second column, not served as a separate page.

```python
j = requests.post(API + slug, headers=HEADERS, verify=False, timeout=60).json()
soup = BeautifulSoup(find_key(j, 'body_en'), 'html.parser')
rows = [tr.find_all(['td', 'th']) for tr in soup.find('table').find_all('tr')]
```

There is no `<thead>`/`<tbody>` and no `<th>` — **every cell is a `<td>`**, row 0 is the header.
No pagination, no "show more", exactly **one table per payload** on all five lists.

If a browser is ever needed instead, the correct selector is **`div.contentSection table`** —
the page also renders a FullCalendar widget with three decoy `<table>`s outside
`contentSection`. The scraper does not need a browser and does not use one.

---

## Lists

| ListNr | ListCode | ListLabel | ListName | Source field | Rows |
|---|---|---|---|---|---|
| 1 | `1` | 2 | List of Life Insurers | `body` (Bengali) + translation | **36** |
| 2 | `2` | 2 | List of Non-Life Insurers | `body_en` | **46** |
| 3 | `3` | 3 | List of Life Bancassurance Institutions | `body` for identity, `body_en` joined in | **12** |
| 4 | `4` | 3 | List of Non-Life Bancassurance Institutions | `body_en` | **7** |
| 5 | `5` | 2 | List of Authorized Insurtech Institutions | `body_en` | **7** |

**Total 108 rows.** Every list carries a visible serial-number column, and the emitted count
equals the site's last serial on all five. The scraper prints
`emitted N vs table M` and warns on any mismatch, plus a second warning if the count drifts
from the values above.

`ListCode` is the ListNr as a plain string (`'1'` … `'5'`), pinned to text on write-out.
`RegCtry`/`RegCode`/`ListCode` are the three tokens of `'BD IDRABD <n>'`, split from the
`regdict` key — never re-typed.

### Column layouts (verified against the live payloads)

| List | Cols | Layout |
|---|---|---|
| 1 | 11 | `0` SL · `1` insurer name (bn) · `2` head-office address (bn) · `3` CEO (bn) · `4` CEO (en) · `5` CEO mobile · `6` CEO email · `7` chairman (en) · `8` chairman (bn) · `9` chairman mobile · `10` chairman email |
| 2 | 3 | `0` SL · `1` **name + address + phone + website crammed into one cell** · `2` CEO block |
| 3 | 6 | `0` SL · `1` corporate agent (the bank) · `2` partner insurer · `3` licence no. · `4` issue date · `5` hotline |
| 4 | 6 | same as list 3, but the licence number is bare (`01/2024`, no `Corporate Agent ` prefix) |
| 5 | 6 | `0` Serial · `1` company · `2` address · `3` CEO · `4` mobile · `5` email |

Lists 1, 2 and 5 publish **no licence number and no issue date**. Lists 3 and 4 publish
**no address, no email and no website**. That is the source, not a parsing gap — it explains
the fill rates in the QA section.

---

## Four traps in this source, and what v2 does about each

### 1. `body_en` for list 1 is not English

`body_en` on list 1 is a copy of the Bengali. Measured: of its 407 cells only 4 differ from
`body`, the insurer-name column is **36/36 Bengali in both**, and even the headers are Bengali.

The ticket asks for list 1 to be translated "if possible", so v2 machine-translates the name
and the head-office address (bn → en). **The translations are baked into the script as an
84-entry cache**, so the production run needs no translation library and no extra network
call. `googletrans` is consulted only for strings IDRA adds later; if it is missing or blocked
the run degrades to keeping the Bengali string and carries on — it never dies on translation.

Rows whose Name came from machine translation are flagged **`ListLanguage = 'BN'`**; rows where
IDRA itself published the English name are `'EN'`. This keeps "the regulator says so" and
"a machine guessed" distinguishable downstream:

| ListCode | `EN` | `BN` (machine-translated) |
|---|---|---|
| 1 | 0 | 36 |
| 2 | 46 | 0 |
| 3 | 9 | 3 |
| 4 | 7 | 0 |
| 5 | 7 | 0 |

#### The cache was human-reviewed on 2026-09-02, and six entries were wrong

All 39 machine-translated names were checked against the [Bangladesh Insurance Association
life-insurer directory](https://biabd.org/wp-content/uploads/2024/07/) and the companies' own
sites. Thirty-three transliterations were right. Six were not, and the failure mode is always
the same: **googletrans translated a proper noun instead of transliterating it.**

| Bengali | was | corrected to | why it matters |
|---|---|---|---|
| সন্ধানী লাইফ | `Thanthi Life Insurance Co. Ltd` | **Sandhani** Life Insurance Co. Ltd | not even phonetically close; matches nothing |
| জীবন বীমা কর্পোরেশন | `Life Insurance Corporation` | **Jiban Bima Corporation** | collided with a different company — see below |
| প্রগতি লাইফ | `Progress Life Insurance Plc.` | **Pragati** Life Insurance Plc. | প্রগতি = "progress", but it is the company's name |
| আকিজ তাকাফুল | `Akiz Takaful` | **Akij** Takaful | Akij Group; BIA and akijtakafullife.com.bd |
| আলফা ইসলামী | `Alfa Islami` | **Alpha** Islami | alphalife.com.bd, BIA "Alpha Islami Life Insurance Ltd." |
| ফারইস্ট ইসলামী | `Far East Islami` | **Fareast** Islami | official spelling is one word |

Two `Address_1` values carried the same proper nouns and were corrected with them
(`Far East Tower` → `Fareast Tower`; `Thanthi Life Tower, … Banglamator` →
`Sandhani Life Tower, … Bangla Motor`).

**The Jiban Bima one was a genuine data defect, not a cosmetic one.** জীবন বীমা কর্পোরেশন is
the state-owned life corporation (JBC, jbc.gov.bd, established 1973). Translated to
"Life Insurance Corporation" it became near-identical to row 29,
`Life Insurance Corporation (LIC) of Bangladesh Limited` — the Indian LIC's Bangladesh
subsidiary, licensed 2015. Two unrelated entities, one name. Row counts would never have
caught it.

`validate_content()` now asserts the bad forms never reappear, because the live-translation
fallback would silently re-introduce them the moment IDRA edits one of the cached strings.
Anyone regenerating the cache from googletrans must re-apply these six by hand.

### 2. List 3's English is STALE — using it silently drops 3 licensees

`body` has **12** rows; `body_en` has **9**. The English rendering stops at
`Corporate Agent 09/2024` (Pubali Bank, 30/10/2024) and is missing the three 2025 licensees
present in Bengali: **Premier Bank PLC (02/2025), Midland Bank PLC (01/2025),
UCB Bank PLC (03/2025)**.

So for the bancassurance lists **`body` is authoritative for row identity**, and English names
are joined in from `body_en` **on the licence number** (`NN/YYYY`, after normalising Bengali
digits). The three rows with no English match are translated. The scraper records this as
`stale_en_3 : 9 en vs 12 bn` and `bn_only_3 : 3` so the divergence is visible in the log rather
than silent. Lists 2, 4 and 5 have matching counts in both languages.

### 3. List 4 has 3 malformed continuation rows

List 4's table has **11 `<tr>` but only 7 entities**. Rows at index 2, 3 and 6 are a
**single `<td>` with no `colspan`** holding an extra partner insurer belonging to the row above
(City Bank PLC owns Reliance + Pioneer + City General; BRAC Bank owns Green Delta + Pioneer).
Naive `find_all('tr')` parsing either crashes on `cells[1]` or emits 10 junk rows. `entity_rows()`
filters on `len(cells) > 1`. The site's own serial column runs 1–7, so **7 is the number to
match** — and 7 is what v2 emits.

### 4. List 2 crams one entity into one cell, and 8 names wrap

The whole entity — name, address, phone(s), website — is a stack of `<p>` blocks in a single
cell, with **no `<br>`**. Splitting is necessarily heuristic: line 0 is the name, a line with
`@` is the email, one with `www`/`http` is the website, a line with ≥7 digits that does not look
like a street line is a phone, the rest is the address.

Two observed wrinkles, both handled:

- A `<sup>` splits floor numbers into their own block —
  `'Rupayan trade cen'`, `'th'`, `'Floor), 114-115 …'` is **one** address. `rejoin_ordinals()`
  re-attaches `th`/`st`/`nd`/`rd`/`&` fragments.
- **8 of the 46 names wrap onto a second block holding only the corporate suffix**
  (`'Asia Pacific General Insurance'` + `'PLC'`). Without re-joining, those 8 names are
  silently truncated — this was a genuine bug caught in QA, not a hypothetical.
  `NAME_SUFFIX_RE` re-attaches them and the run reports `list2_name_rejoined : 8`.

---

## Field mapping

| Schema field | Source |
|---|---|
| `Name` | list 1 → translated insurer name; list 2 → first `<p>` (+ wrapped suffix); lists 3/4 → corporate agent (the bank), English joined on licence no.; list 5 → company name |
| `Address_1` | list 1 → translated head office; list 2 → residual `<p>` blocks; list 5 → address column. **Empty on lists 3/4 — not published.** |
| `City`, `Zip` | derived from `Address_1` (BD city vocabulary + the 4-digit BD postcode in `Dhaka-1000` form) |
| `Phone` | list 1 → CEO mobile *(see below)*; list 2 → phone lines, `; `-joined; lists 3/4 → hotline short code (e.g. `16234`); list 5 → mobile |
| `Email` | list 1 → CEO email (company domain); list 2 → CEO block; list 5 → email column |
| `Website` | list 2 only — the only list that publishes one |
| `InternalID_1` / `_type` | lists 3/4 → licence number (`Corporate Agent 01/2024` / `01/2024`), type `License Number` |
| `RegulationDate` | lists 3/4 → licence issue date, `dd/mm/yyyy` → ISO (`05/02/2024` → `2024-02-05`) |
| `CoType` | per-list constant: `Life Insurer` / `Non-Life Insurer` / `Bank` / `Bank` / `Insurtech Company` |
| `License_Type` | per-list constant, e.g. `Life Bancassurance Corporate Agent` |
| `Cntry`, `RegCtry`, `RegCode` | `'BD'`, `'BD'`, `'IDRABD'` |
| `RegulationType` | `'Regulated'` — all five are positive registers of licensed entities |
| `ListCode`, `ListName`, `ListLabel` | per-list constants from the table above |
| `ListLanguage` | `'EN'` where IDRA published English, `'BN'` where machine-translated |
| `ListProcessDate` | `datetime.datetime.now().strftime('%Y-%m-%d')` |
| `ListValidityDate` | **empty** — IDRA publishes no "as of" date on any of the five pages |

### Deliberate omissions

Three source fields have **no slot in the fixed 43-key schema** and are dropped rather than
forced into a field that means something else:

- **Partner insurance company** (lists 3/4, column 2) — it is a commercial counterparty, not a
  parent, so `Name - Mother Company` would be wrong. This includes the extra partners carried
  by list 4's continuation rows.
- **CEO / chairman names** (lists 1, 2, 5) — no person field exists.
- **Chairman mobile and email** (list 1, columns 9–10).

### One judgement call worth knowing about

**List 1's `Phone` is the CEO's mobile.** IDRA publishes no switchboard number for life
insurers — columns 5 and 9 are the CEO's and chairman's personal mobiles. v2 uses the CEO
mobile because it is the only contact number the regulator publishes for the entity. If the
convention is that `Phone` must be a corporate line, list 1's `Phone` should be blanked; say so
and it is a one-line change. The emails (`ceo@akijtakafullife.com.bd`) are on company domains
and are not affected by this concern.

---

## ListLabel justification — lists 3, 4 and 5 NEED CONFIRMATION

The ticket does not specify ListLabel. These are my application of the house rule
(1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else):

- **Lists 1, 2 → `2`.** Life and non-life insurers. Risk carriers, unambiguous.
- **Lists 3, 4 → `3`. Flagged.** The listed entities are **banks** (City Bank PLC, Eastern Bank
  PLC, Standard Chartered Bank, BRAC Bank PLC …) that hold a bancassurance corporate-agent
  licence from the **insurance** regulator. `3` is exactly the "bank & insurance" case. But an
  argument for `2` exists (it is an insurance-distribution register) and for `1` (the entity is
  a bank). This repo has precedent pulling both ways — ID OJK labels rep offices of foreign
  banks `1` "on entity kind", and labels insurance intermediaries `2` "following the sector".
  **Please confirm.**
- **List 5 → `2`. Flagged.** Insurtech companies are insurance intermediaries, not carriers.
  I followed the ID OJK precedent that puts insurance intermediaries (brokers, loss adjusters)
  at `2`. `4` is defensible if the label is meant to capture underwriters only.

Note the practical consequence: 3 banks (**City Bank PLC, Eastern Bank PLC, Mutual Trust Bank
PLC**) appear in **both** list 3 and list 4, under different licence numbers. That is 6 rows for
3 legal entities and it is **correct** — they are separate licences on separate registers.
Do not dedupe them; the row count would then stop matching the site.

---

## QA — verified results (run of 2026-09-02, 108 rows)

**No `qa_positive_combined/` baseline exists for BD IDRABD** (the directory holds only
`README.md`, `qa_positive_weekly_merge.ipynb` and `tempfolder`), so the fallback checks were
used.

Verdict: **CLEAN — NO BASELINE, FALLBACK CHECKS PASSED.**

| Check | Result |
|---|---|
| Schema | 43 keys, correct order, `add_row()` rejects any key outside them |
| Row count vs site | 36 / 46 / 12 / 7 / 7 — **all five match the site's own serial count** |
| `Name` content | 108/108 non-empty, **0 junk** (no numeric-only, no `Yes`/`No`, no dates, no mojibake, none under 3 chars) |
| Encoding | `Ã©` 0 · `â€™` 0 · `Â ` 0 · `?{3,}` 0 · **residual Bengali cells 0** |
| Excel round-trip | 8 text-pinned columns, 408 digit cells read back and verified; 0 float-coerced |
| Constants | `RegCtry`=BD, `RegCode`=IDRABD, `Cntry`=BD, `RegulationType`=Regulated, `ListProcessDate` uniform |

Required-field non-empty rates — **overall, then why**:

| Field | Non-empty | Explanation |
|---|---|---|
| `Name` | **108/108 (100 %)** | — |
| `Cntry` | **108/108 (100 %)** | constant `BD` |
| `Phone` | 95/108 (88 %) | list 2 source has a phone line in only 34 of 46 cells — **we captured 34/34** |
| `Address_1` | 89/108 (82 %) | lists 3/4 (19 rows) publish no address |
| `City` | 84/108 (78 %) | derived from address; absent wherever the address is |
| `Website` | 46/108 (43 %) | **only list 2 publishes a website** — 46/46 there |
| `InternalID_1` | 19/108 (18 %) | **only lists 3/4 publish licence numbers** — 19/19 there |

The three low rates are structural properties of the source, each measured against the source
rather than assumed. The list-2 phone rate in particular was checked cell-by-cell against the
live payload: 34 of 46 cells contain a phone-like line and the parser found all 34.

### Assertions that run in the production path

- `add_row()` raises `KeyError` on any field outside the 43 and asserts all 43 columns stay the
  same length after every append.
- `qa_dataframe()` asserts `Name` **content**, not just row counts — a previous regulator in
  this repo reconciled 997/997 rows with `Name` full of `Yes`/`No`.
- Excel round-trip: ID/Zip/Phone/ListCode/ListLabel pinned to text, the workbook read back, and
  every digit cell compared before/after.
- Mojibake gate across all columns before writing.
- Per-list row counts printed **ASCII-only**; raw Bengali is never printed, because the
  production Windows console is cp1252.
- Any failed list is collected in `FAILURES`, the workbook is still written for the lists that
  worked, and the script exits **2**.

---

## Output

Saved to the **regulator folder**, not `tempfolder/`:

```
BD IDRABD/BD IDRABD SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx     sheet "SQL Ready"
```

`tempfolder/` is created if missing but this regulator downloads nothing, so it stays empty.

---

## NEEDS CONFIRMATION FROM TICKET OWNER

1. **ListLabel for lists 3, 4 (`3`) and 5 (`2`)** — see the justification section.
2. **List 1 `Phone` = CEO mobile.** Acceptable, or should it be blank when no corporate line is
   published?
3. **The partner insurance company on lists 3/4 is dropped** for lack of a schema slot. If it is
   wanted, say which of the 43 fields should carry it.
4. **List 3's three Bengali-only rows** (Premier / Midland / UCB) carry machine-translated names
   and `ListLanguage = 'BN'`. Confirm that is preferred over holding the Bengali original.
5. **The 3 banks that appear in both list 3 and list 4** are kept as 6 rows. Confirm that is
   wanted (it is what the site shows).

---

## Known limitations

- **The translation cache is a snapshot.** 84 Bengali strings translated on 2026-09-02. New
  entities IDRA adds will miss the cache; the script then tries `googletrans` live and, failing
  that, keeps the Bengali string and flags `translate_miss`. It will not crash, but a Bengali
  name can reach the output that way — the QA mojibake/Bengali scan will show it.
- **List 2's parsing is heuristic** because the source is one unstructured cell. It is verified
  correct on all 46 current rows, but a new row formatted differently (a phone line that reads
  like a street address, or a name wrapping onto a suffix not in `NAME_SUFFIX_RE`) could be
  mis-split. This is the most likely place for a future regression.
- **`City`/`Zip` are derived, not published.** The BD city vocabulary is a fixed list; an entity
  in a town not on it gets an empty `City`.
- **`ListValidityDate` is empty for all five lists** — IDRA publishes no "as of" date.
- **Machine-translated *names* are now human-reviewed; the *addresses* are not.** All 39 `BN`
  names were checked one by one on 2026-09-02 against the Bangladesh Insurance Association
  directory and company sites, and six were corrected (see "The cache was human-reviewed"
  above). The head-office addresses that travel with them were only corrected where they
  carried one of those six proper nouns — the rest are still raw googletrans output, and the
  same translate-instead-of-transliterate failure can be expected in street and building names
  (`Banglamator` for বাংলামটর was one such, found only because it sat next to a bad company
  name). Two cosmetic items were left alone deliberately: BIA writes the acronym `BAIRA` in
  caps where the cache has `Baira`, and four names (Guardian, Golden, Best, Sunflower) came
  back ALL-CAPS while the rest are Title Case.
- **Never run on the Windows control server.** The site was reachable and the full pipeline ran
  from the development Mac; the production box has not been tried. `verify=False` and the
  unverified-SSL default are set for the corporate TLS proxy and are harmless there. Nothing in
  the script needs a browser, which removes the usual production risk.
