# CN CSRC — China Securities Regulatory Commission (中国证券监督管理委员会)

Jira: **DECD-6835**  ·  RegCtry `CN`  ·  RegCode `CSRC`

CSRC supervises securities, futures and funds. Banking and insurance sit with **NFRA**
(see `CN NFRA/`), so there is no overlap between the two tickets.

Production scraper: **`CN_CSRC_v7.py`** (`python3 CN_CSRC_v7.py`).
Notebook: **`CN_CSRC_v7.ipynb`** — generated from the `.py`, cells split on the
`#---- Begin_XXX ----` markers; the two are asserted line-for-line identical.

Observed run **2026-09-03**: **1,502 rows**, output
`CN CSRC SQL Ready 2026-09-03 15.09.40.xlsx`.

> **The Jira ticket's targets are out of date.** The ticket points at the CSRC *English*
> site (`/csrc_en/`), which v5 and v6 scraped. Those five pages serve tables lifted out of
> the **2020 CSRC Annual Report**, published 2021-12-08/09 and never reissued — 997 rows
> frozen five years ago. The ticket owner confirmed this on 2026-09-03 and directed that
> `CN CSRC_v4.ipynb`'s targets (the live Chinese registers) be followed instead.
> **v7 implements that.** v5/v6 are kept on disk as history; do not run them.

---

## Lists

Every register is an Excel attachment on the Chinese site, reissued roughly monthly with
the edition stamped into the article title (`（2026年6月）`). Row counts are from the
2026-09-03 run.

| ListNr | ListCode | ListLabel | ListName | Chinese register | Edition | Article | Rows |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 4 | List of Securities Companies | 证券公司名录 | 2026-06 | `c101900/c1029659` | **150** |
| 2 | 2 | 4 | List of Futures Companies | 期货公司名录 | 2026-07 | `c101920/c1039268` | **150** |
| 3 | 3 | 4 | List of Fund Management Companies | 公募基金管理机构名录 | 2026-06 | `c101900/c1029657` | **179** |
| 4 | 4 | 4 | List of QFIIs | 合格境外投资者名录 | 2026-07 | `c101900/c1029652` | **999** |
| 5 | 5 | 1 | List of Custodian Banks for Qualified Foreign Investors | 合格境外投资者托管行名录 | 2026-07 | `c101900/c1029654` | **24** |
| | | | | | | **TOTAL** | **1,502** |

`ListName` and `Typology` keep the English names used by **v4**, which the ticket owner
pointed at as the reference. Note v6 had shortened list 5 to *List of Custodian Banks*;
v7 restores v4's longer form. Note also that the Chinese register behind list 3 is now
titled **公募基金管理机构名录** (*public-offering fund management institutions*), which is
broader than the English *List of Fund Management Companies* — see
[List 3 has three worksheets](#list-3-has-three-worksheets).

`ListValidityDate` is the article's own `<meta name="PubDate">` — `2026-08-22` for lists
1, 3, 4 and 5, `2026-08-24` for list 2. That is a real observed date; the edition label
(`2026年6月`) has month granularity only and is **not** padded into a fake day-of-month
unless the meta tag is missing, which it was not on any of the five articles.

### ListLabel justification

House rule: **1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.**

- **Lists 1, 2, 3 → `4`.** Securities brokers, futures brokers and fund/asset managers are
  neither banks nor insurers.
- **List 4 (QFIIs) → `4`.** A foreign-investor licence register, not a banking register —
  it mixes asset managers, sovereign and pension funds, universities, insurers and some
  banks, plus three supranationals (IMF, IFC).
- **List 5 (Custodian Banks) → `1`.** All 24 rows are licensed banks (HSBC China,
  Citibank China, ICBC, BoC, Deutsche Bank China, DBS China …). Pure banking.

### CoType

| ListCode | CoType | Rows |
|---|---|---|
| 1 | `Securities Company` | 150 |
| 2 | `Futures Company` | 150 |
| 3 | `Fund Management Company` | 150 |
| 3 | `Asset Management Institution Qualified for Public Fund Offering` | 29 |
| 4 | `Qualified Foreign Institutional Investor` | 999 |
| 5 | `QFII Custodian Bank` | 24 |

List 3's CoType is chosen **per worksheet**, by matching `资产管理机构` in the sheet name —
not by sheet position, so an added or reordered tab cannot silently mislabel a block.

---

## `Name` is what CSRC publishes — nothing is translated

**Decision (ticket owner, 2026-09-03).** `Name` carries the source's own name column, per
list:

| Lists | Source column | `Name` | `ListLanguage` |
|---|---|---|---|
| 1, 2, 3 | 公司名称 / 期货公司名称 | Chinese, verbatim | `ZH` |
| 4, 5 | 英文名称 | CSRC's official English | `EN` |
| 4 (20 rows) | 中文名称 | Chinese — no English is published for these | `ZH` |

CSRC publishes **no English name at all** for lists 1–3, and publishes an official
`英文名称` column for lists 4 and 5. So `Name` is Chinese on 499 rows and English on 1,003.

`ListLanguage` describes the language of **that row's `Name`**, which is why list 4 is not
uniformly `EN`: 20 of its 999 rows have an empty `英文名称` (they are Hong Kong subsidiaries
of mainland fund houses — 博时基金（国际）有限公司, 华夏基金（香港）有限公司, …). Those rows
fall back to the Chinese name rather than being dropped.

### Why not translate, as v4 did

v4 ran every name through `googletrans` and wrote the English into `Name`, parking the
Chinese in **`Name - Mother Company`**. v7 does neither:

- `Name - Mother Company` means **parent company** in the 43-key schema, not "the same name
  in another language". Filling it with the entity's own name asserts a relationship the
  source does not state. It is left empty on all 1,502 rows.
- A machine translation is not the published name. It varies with the translation engine
  and cannot be checked against the source page, which is the QA method actually used here.
- v4's loop slept 5 s per name; at ~465 Chinese names that is over half an hour of the run
  spent producing data the regulator never published.

---

## List 3 has three worksheets

**Decision (ticket owner, 2026-09-03): all three are in scope — 150 + 15 + 14 = 179 rows.**

| Worksheet | Rows | CoType |
|---|---|---|
| `基金管理公司名单` | 150 | Fund Management Company |
| `' 取得公募资格的资产管理机构'` *(note the leading space)* | 15 | Asset Management Institution Qualified for Public Fund Offering |
| `'取得公募资格的资产管理机构'` | 14 | Asset Management Institution Qualified for Public Fund Offering |

The last two tabs are two vintages of the same asset-manager register. Measured overlap:
**8 names appear identically in both**, 7 are only in the 15-row tab, 6 are only in the
14-row tab — **21 distinct firms across 29 emitted rows**.

Some of the differences are renames (`中银国际证券有限公司` → `中银国际证券股份有限公司`,
`国都证券有限责任公司` → `国都证券股份有限公司`), and the 15-row tab carries
`上海国泰海通证券资产管理有限公司`, the entity created by the 2025 国泰君安 / 海通 merger.
But **neither tab is a superset of the other** — the 14-row tab holds
`泰康资产管理有限责任公司` and `东兴证券股份有限公司`, which the 15-row tab does not. Dropping
either tab would lose real entities, which is why all three are emitted.

**There is no deduplication step, by design.** 16 of the 179 rows are exact-duplicate names
(the 8 firms above, once per tab). QA here is done by counting rows at the source, so a
row present twice in the workbook is emitted twice.

---

## How the current edition is found at runtime

**Nothing about the edition is hard-coded** — not the article id, not the attachment
filename, not the year or month. The constants are the host, the five Chinese register
titles, and the five ListNames.

1. **Search, not a fixed URL, and not a channel walk.**
   `POST /guestweb4/s` with `searchWord=<register title>`, `uc=1`, `siteCode=bm56000001`,
   `column=全部`.
   - A hard-coded `content.shtml` goes stale the moment CSRC publishes the next month's
     edition — every reissue gets a brand-new article id.
   - A channel listing cannot cover the set either: **期货公司名录 lives in channel
     `c101920` while the other four live in `c101900`**, so there is no single channel that
     holds all five. (Fourteen candidate channel ids under `c101920` were tested; none
     returns the futures register at the top of its listing.)
2. **Selection is by title, never by position.** Keep only hits whose `title` attribute
   *starts with* the register's exact Chinese stem. This is what separates
   `合格境外投资者名录` from `合格境外投资者托管行名录` — a substring test would confuse them.
   Then read the `（YYYY年M月）` edition out of the title and take the newest. A hit with no
   parseable edition is ignored rather than ranked.
   Both bracket styles are accepted: **list 4's title closes with an ASCII `)` while opening
   with a full-width `（`** (`合格境外投资者名录（2026年7月)`).
3. **Article → attachment + date.** The first `href="….xls|.xlsx"` on the article page is
   resolved with `urljoin` + `quote(safe='/:%')`. The filenames are percent-encoded Chinese
   under a per-publication folder
   (`/csrc/c101900/c1029659/1029659/files/%E8%AF%81%E5%88%B8…`), so they change every month.
   `safe='/:%'` is what stops an already-encoded name being double-encoded.
   The publication date comes from `<meta name="PubDate" content="2026-08-22 19:47:09"/>`.
4. **Format from magic bytes, not from the extension.** `\xd0\xcf\x11\xe0` (OLE2) → the
   `xlrd` engine; `PK` (zip) → `openpyxl`. All five current files are real `.xls`. Trusting
   the `.xls` in the URL would pick the wrong engine the first time CSRC ships a renamed
   `.xlsx`. Anything else raises.

### The trap that cost a run: a CRLF inside the `href`

The search results emit

```
href="//www.csrc.gov.cn/csrc/c101900/c1029659/content.shtml\r\n"
```

— with a literal carriage-return + newline **inside the attribute value**. Left in place it
is sent as part of the request path; the server answers **200** with a page that simply has
no attachment on it, and the run then fails three steps later with
`no .xls/.xlsx attachment on …`, blaming the article instead of the parser. `tag_attrs()`
strips every attribute value for this reason.

Encoding: `decode_bytes()` decodes `r.content` explicitly as utf-8 then gb18030 and never
trusts `r.encoding` — Chinese government sites routinely misdeclare their charset. Every
request uses `verify=False` (a cert error here is the corporate TLS proxy, not the site) and
retries 4× with escalating backoff on one shared `requests.Session`.

---

## How the workbooks are parsed

Plain `pandas`. No pdfplumber, no OCR, no browser driver — the sources are real Excel files.
The parsing is deliberately **label-driven and shape-agnostic**, because every positional
assumption in this register family has already rotted at least once:

- **Every worksheet is examined; none is named in code.** List 2's data is on `Sheet3`, not
  `Sheet1`. List 5 carries two empty trailing sheets. List 3's two asset-manager tabs have
  names differing **only by a leading space**. Selecting sheets by name would need all of
  that hard-coded, and would break at the next reissue.
- **The header row is found, not assumed.** The first row within the top 6 containing a
  `序号` cell is the header. v4 assumed row 0; the current QFII sheet puts a title note on
  row 0 and the header on row 1, so v4's assumption would take the note as column names.
- **Columns are mapped by label.** Suffix order matters —
  `合格境外投资者托管行中文名称` ends with **both** `名称` and `中文名称`, so the specific
  suffixes are tested first.
- **A row is a register row only if its `序号` cell is a small integer.** That single rule
  drops the QFII sheet's row-0 title note, the blank spacer rows, and the trailing
  `注：1. …` footnote — without any of them being enumerated in code.
- **Excel numerics are normalised before that test.** `xlrd` returns a `序号` of 1 as the
  float `1.0`; unnormalised it fails the integer test and the row is *silently dropped*
  rather than raising. Whole floats are converted to their integer form first.
- **The merged-cell forward-fill is applied to `City` only.** List 2 groups rows under one
  merged `辖区` cell, which reads as blank on every row but the first of the merge, so it is
  filled down. It is **not** applied to the QFII `注册地` column: that column is a *country*,
  and two of its rows are genuinely blank — filling those down would invent a nationality.

`pandas.DataFrame.map` is used where available (pandas ≥ 2.1) with a fallback to
`applymap`, so the same file runs on the control server's older pandas and on pandas 3.x.

---

## Field mapping

| Source column | → sqldict field | Note |
|---|---|---|
| 公司名称 / 期货公司名称 (lists 1–3) | `Name` | Chinese verbatim, `ListLanguage='ZH'` |
| 英文名称 (lists 4, 5) | `Name` | CSRC's official English, `ListLanguage='EN'` |
| 中文名称 (list 4, 20 rows) | `Name` | fallback where no English is published, `ListLanguage='ZH'` |
| 序号 | `InternalID_1` + `InternalID_1_type = 'CSRC list sequence number'` | forced to text before `to_excel` |
| 辖区（注册地） / 辖区 / 注册地 (lists 1–3) | `City` | verbatim; see the caveat below |
| 注册地 (list 4) | `Cntry` | Chinese country name → ISO-3166 alpha-2 via `CNTRY_MAP` |
| 批准日期 (list 4) | `RegulationDate` | `2003-05-23 00:00:00` → `2003-05-23`; 999/999 populated |
| 主托管行 (list 4) | *not mapped* | see [Judgment calls](#judgment-calls-for-the-requester) |
| 办公地 (list 3, third tab) | *not mapped* | equals 注册地 on 13 of that tab's 14 rows |

Constants: `RegCtry='CN'`, `RegCode='CSRC'`, `ListCode=<ListNr>`,
`RegulationType='Regulated'` (all five are positive authorisation registers),
`ListProcessDate=<run date>`, `Cntry='CN'` for lists 1, 2, 3 and 5.
`Name - Mother Company` is empty on all 1,502 rows.

All 43 keys are written through a single `add_row(**kw)` funnel: an unknown key raises, and
column lengths are asserted equal after every append, so the schema cannot drift and a
mis-sequenced append cannot silently misalign a row.

### `City` on lists 1–3 is a supervisory jurisdiction, not always a city

The source column is **辖区（注册地）** — the CSRC regional-bureau jurisdiction, which doubles
as the place of registration. It is taken verbatim, and 54 distinct values were observed.
Two things to know downstream:

- **Many values are provincial, not municipal** — `广东`, `江苏`, `内蒙古`, `新疆`, `西藏`
  sit alongside genuine cities (`北京`, `上海`, `深圳`, `大连`, `宁波`, `厦门`, `青岛`).
- **Some values are compound strings** where the bureau and the registered office differ,
  e.g. `北京（注册地上海）` ("Beijing bureau, registered in Shanghai") and
  `深圳（注册地广州）`. These are kept as published rather than split, because splitting them
  would require choosing which half is the "city" — a decision the source does not make.

`City` is blank on lists 4 and 5, which publish no location column at all.

### `Cntry` on list 4

The QFII `注册地` is the investor's **home jurisdiction**, not China: HK 361, SG 154, US 91,
GB 74, KR 49, TW 40, JP 21, FR 20, AU 20, CH 19, AE 16, CA 14 … across 45 mapped countries.

**996 of 999 rows are mapped. The other three are left blank, never guessed:** seq 433
*International Monetary Fund*, seq 439 *International Finance Corporation* and seq 744
*International Monetary Fund Investment Fund*. Two have an empty `注册地` and one is filed
under `国际组织` ("international organisation"), which has no ISO-3166 code. *(v6 assigned
these `CN` by default, which was wrong; v7 leaves them blank and reports them.)*

Any `注册地` value not in `CNTRY_MAP` leaves `Cntry` blank and is printed at the end of the
run with its row count — it is never approximated.

---

## Acceptance tests

Run automatically before and after `to_excel`. These **fail the run**; only baseline drift
warns.

1. **43-key schema** — `list(df.columns) == SCHEMA_KEYS` and `len(df.columns) == 43`.
2. **Sequence contiguity, per worksheet** — each sheet's `序号` must be exactly `1..n`. This
   is the check that catches a dropped or mis-filtered row, and it is per-sheet rather than
   per-list because list 3's numbering restarts on each tab. All five lists reported
   `seq 1..n OK` on 2026-09-03.
3. **Baseline row counts** — 150 / 150 / 179 / 999 / 24. Reported as a **warning**, not a
   failure: these registers are reissued monthly and are *expected* to drift.
4. **Mojibake gate** — zero `Name` values matching `[�]|Ã.|â€|ï¿½`. This matters more than
   usual here: 499 Names are Chinese, and a charset mistake produces plausible-looking rows
   that every count-based check passes.
5. **Name content gate** (`name_defects()`) — zero Names that are empty, `yes`/`no`/`nan`, a
   date, a bare integer, a leaked header (`公司名称`, `中文名称`, `序号`), or a table title
   (`Table …`, `List of …`, anything containing `名录`/`名单`).
   **This rule had to change from v6.** v6 required "at least 3 alphabetic characters", which
   is a Latin-alphabet test — `国泰基金管理有限公司` contains zero Latin letters, so v6's gate
   would have rejected every row on three of the five lists. v7 requires **2+ CJK characters
   or 3+ Latin letters**.
6. **Language gate** — every `ListLanguage='ZH'` row's `Name` must contain a CJK character,
   and every `EN` row's `Name` a Latin letter. This is what would catch a name/language
   column swap, which no count-based check can see.
7. **Non-blank constants** — `RegulationType`, `ListProcessDate`, `ListValidityDate`,
   `RegCtry`, `RegCode`, `ListCode`.
8. **Excel round-trip** — the workbook is read back with `dtype=str` and asserted for row
   count, column order, `InternalID_1` still a digit string (Excel coerces all-digit strings
   to floats and eats leading zeros), `RegCode == 'CSRC'`, the Name content gate re-run, and
   **the count of Chinese Names unchanged**.

### Why the Name gates exist

`CN CSRC SQL Ready 2026-08-20 19.59.19.xlsx` (v5) reconciled **997/997 rows** while **96 of
its Names were the wrong column** — 72 carried the source's `Branch in Hong Kong SAR`
Yes/No flag, 23 carried the approval date, and 1 carried the table title. A wrong column
still produces exactly one value per row, so row-count reconciliation cannot see it. That
is the whole reason `Name` is asserted on **content**, separately from the row counts.

---

## Console safety (Windows production)

The control server runs **Python 3.8** with a **cp1252** console, which cannot encode a
single Chinese character — printing raw scraped text raises `UnicodeEncodeError` in
`encodings\cp1252.py`. This scraper is ~a third Chinese data, so:

- everything reaching `print()` goes through `ascii_slug()` (non-ASCII → `?`, truncated),
  including sheet names, unmapped country values and assertion payloads;
- **lists are identified in the log by their English `ListName` and their ASCII URL**, never
  by their Chinese title — which is why list 3's log lines read
  `sheet : ????????   rows 150` rather than the sheet name. That is intentional, not a bug.

`CN_CSRC_v7.py` is verified with `ast.parse(src, feature_version=(3,8))` — no walrus, no
`match`, no `dict |` merge, no 3.9+ syntax.

---

## Verified vs not verified

**Verified — a full end-to-end run on 2026-09-03** (macOS, repo `.venv` Python 3.13.14,
pandas 3.0.3, xlrd 2.0.2, requests 2.34.2):

- all five registers discovered by search, correct editions, correct article ids;
- 1,502 rows emitted, every list matching its baseline, every sheet `seq 1..n OK`;
- all eight acceptance tests passed, including the Excel round-trip;
- the notebook's concatenated code is line-for-line identical to the `.py` and compiles.

**Not verified:**

- **This has never been run on the Windows control server.** In particular `xlrd` is assumed
  present there — v4 used `engine='xlrd'` and did run on that box, but that was an older
  build and it has not been rechecked.
- The `applymap` fallback path was not exercised: the run used pandas 3.0.3, which has
  `DataFrame.map`. The fallback is there for the control server's older pandas and is
  untested.
- The `openpyxl` branch of `download()` was not exercised — all five current attachments are
  OLE2 `.xls`.
- The `ListValidityDate` fallback (edition + `-01`, used only when the `PubDate` meta tag is
  missing) was not exercised; all five articles carried the tag.

---

## Known limitations

1. **`City` is a jurisdiction, sometimes provincial, sometimes compound.** See
   [the caveat above](#city-on-lists-13-is-a-supervisory-jurisdiction-not-always-a-city).
   Anything doing city-level matching must account for it.
2. **`Name` is Chinese on 499 rows.** That is what CSRC publishes for lists 1–3; there is no
   English edition of those registers. Downstream matching against a Latin-script master
   will need transliteration or a Chinese-aware matcher.
3. **List 3 contains 16 rows that are exact-duplicate names** (8 firms, once per vintage
   tab), by explicit decision. See [List 3 has three worksheets](#list-3-has-three-worksheets).
4. **`InternalID_1` restarts at 1 on each of list 3's three tabs**, so it is not unique
   within ListCode 3. It is the source's own row number, not a registration number — it is
   emitted for traceability back to the worksheet, not as an identifier.
5. **Three QFII rows have no `Cntry`** (IMF, IFC, IMF Investment Fund). Supranationals have
   no ISO-3166 country. Left blank deliberately.
6. **No address, city, phone, website, email, LEI or licence number is available** for any
   list. These workbooks carry only the columns mapped above; those sqldict fields are
   intentionally blank.
7. **Editions move monthly and independently.** On 2026-09-03 lists 1 and 3 were the June
   edition while 2, 4 and 5 were July. Row counts will drift; the baseline check warns rather
   than fails, and the per-sheet `1..n` contiguity check is what actually guards correctness.
8. **`www.csrc.gov.cn/` in this directory** is a single saved page left over from an earlier
   version. No script references it; it can be deleted.

---

## Judgment calls for the requester

1. **`主托管行` (list 4's custodian bank) is dropped.** Each QFII row names its main
   custodian — 18 distinct values. There is no field for it in the 43-key schema:
   `Name - Mother Company` means *parent*, and a custodian is not a parent. Say the word and
   it can go somewhere, but it needs a deliberate home.
   Note these are **short trade names** (`中国银行`, `汇丰银行`, `法国巴黎银行`), not the
   full legal names on list 5 (`汇丰银行(中国)有限公司`) — **0 of the 18 match a list-5 name
   as a string**, so joining the two lists would need name normalisation, not an equality
   test. They do appear to be the same institutions.
2. **`ListName` for list 3 no longer matches its Chinese source title.** The register is now
   **公募基金管理机构名录** (*public-offering fund management institutions*), which is why the
   workbook carries asset managers as well as fund management companies. The output keeps
   v4's *List of Fund Management Companies*. If the ticket's ListName should be updated to
   match, that is a one-line change.
3. **List 5's `ListName` was restored to v4's longer form**, *List of Custodian Banks for
   Qualified Foreign Investors* (v6 had shortened it to *List of Custodian Banks*). Confirm
   which form the pipeline expects, since it changes the value stored in `ListName`.
4. **`ListLanguage` is per row, not per list** — list 4 is `EN` on 979 rows and `ZH` on the
   20 with no published English name. If the field is meant to describe the *list* rather
   than the row, list 4 should be forced to `EN` throughout.
5. **`RegulationDate` is populated for list 4 only** (CSRC's per-entity 批准日期, 999/999,
   ranging 2003-05-23 → 2026-07-31). The other four registers publish no per-entity date, so
   it is blank there and the publication date is carried in `ListValidityDate` instead.
6. **The negative side is not covered.** These five registers are positive lists only. CSRC
   publishes separate 注销 / 撤销 (deregistration, licence withdrawal) announcements which no
   list here reads. If cancelled entities are wanted they need their own ListNr and a
   non-`Regulated` `RegulationType`; they must not be folded into these five.
