# CN NFRA — National Financial Regulatory Administration (国家金融监督管理总局)

Jira: **DECD-6831**  ·  RegCtry `CN`  ·  RegCode `NFRA`

NFRA was created in 2023 out of the former **CBIRC** (China Banking and Insurance Regulatory
Commission). It supervises banking and insurance; securities remain with CSRC.

Production scraper: **`CN_NFRA_v3.py`** (`python3 CN_NFRA_v3.py`).
Notebook: **`CN_NFRA_v3.ipynb`** — generated from the `.py` and executed end-to-end with nbclient,
zero cells with `output_type == 'error'`.

---

## Lists

All five lists come from the same NFRA publication series (机构名单, "institution lists"),
republished roughly twice a year. Row counts below are from the run of **2026-08-20**.

| ListNr | ListCode | ListLabel | ListName | Source document (current) | Source type | Rows |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | List of Banking Financial Institutions | 银行业金融机构法人名单（截至2025年12月末）, docId 1268142 | PDF attachment, 259 pages | **3619** |
| 2 | 2 | 1 | List of Branches of Foreign Banks | 外国及港澳台银行分行名单（截至2025年12月末）, docId 1268146 | PDF attachment, 7 pages | **114** |
| 3 | 3 | 2 | List of Insurance Institutions | 保险机构法人名单（截至2025年12月末）, docId 1268149 | PDF attachment, 17 pages | **239** |
| 4 | 4 | 2 | List of Foreign Reinsurance Company Branches | 外国再保险公司分公司名单（截至2025年12月末）, docId 1268158 | PDF attachment, 1 page | **8** |
| 5 | 5 | 4 | List of Financial Holding Companies | 金融控股公司法人名单（截至2025年12月末）, docId 1268160 | PDF attachment, 1 page | **3** |
| | | | | | **TOTAL** | **3983** |

`ListValidityDate = 2025-12-31` (the 截至 date in every title).
`RegulationDate = 2026-08-14` (the publication date of all five documents).

### ListLabel justification

- **Lists 1 and 2 → `1` (bank).** Banking legal persons, and branches of foreign / HK / Macau /
  Taiwan banks. Pure banking.
- **Lists 3 and 4 → `2` (insurance).** Insurance legal persons (incl. insurance groups, asset
  managers, mutuals) and branches of foreign reinsurers. Pure insurance.
- **List 5 → `4` (everything else).** 金融控股公司 are non-operating holding vehicles that sit
  *above* banks and insurers. They are neither a bank nor an insurer themselves, so `3`
  (bank & insurance) would overstate what the entity is. **Open judgment call** — see below.
- `3` (bank & insurance) is not used: NFRA supervises both sectors, but it publishes them as
  separate registers, so no single list is mixed.

---

## The URLs in the ticket are dead — CBIRC → NFRA migration

Every URL on DECD-6831 points at:

```
https://www.cbirc.gov.cn/cn/view/pages/zhengwuxinxi/zhengfuxinxi.html#1
```

`www.cbirc.gov.cn` **does not resolve** from our network (the corporate proxy returns
`502 Bad Gateway` on the CONNECT tunnel — i.e. no upstream host, not a proxy policy block).
The same path is live on the new host:

```
https://www.nfra.gov.cn/cn/view/pages/zhengwuxinxi/zhengfuxinxi.html#1   → HTTP 200
```

The whole site was lifted across unchanged: same paths, same AngularJS front end, and the
backend is still mounted at **`/cbircweb/`** (the old application name was never renamed).
The scraper hard-codes only the host `https://www.nfra.gov.cn`; if NFRA ever renames the
backend path, `ITEM_API` / `DOC_API` in the `Variable` cell are the two lines to change.

---

## How it works (and why not the v1/v2 approach)

The page in the ticket is an AngularJS shell — the documents are not in the HTML. There is a
plain JSON API behind it, so **no browser is used at all**:

1. **Discover** — `GET /cbircweb/DocInfo/SelectDocByItemIdAndChild?itemId=863&pageSize=20&pageIndex=N`
   lists the 机构名单 column (declares **136** documents). Paged until the declared total is
   reached. Nothing about which document is current is hard-coded.
2. **Match** — pick the newest document whose Chinese title contains the list's keyword
   (e.g. `银行业金融机构法人名单`). If no title matches, the scraper prints a loud
   `SKIPPED - no document whose title contains '<keyword>'` rather than emitting 0 rows silently.
3. **Resolve the attachment** — `GET /cbircweb/DocInfo/SelectByDocId?docId=<id>` returns
   `attachmentInfoVOList[0].urlOtherName`, e.g.
   `/chinese/docfile/2026/1dcdad9de86f4d9d889356bb64cb313e.pdf`. That filename is a random
   GUID that changes every publication — it is **always** resolved at runtime.
4. **Parse** — `pdfplumber.extract_table()` per page; the header repeats on nearly every page
   and is skipped after the first occurrence.

### What was wrong with v1 / v2

| Problem | v1 | v2 | v3 |
|---|---|---|---|
| Host | `cbirc.gov.cn` (dead) | `nfra.gov.cn` (already patched) | `nfra.gov.cn` |
| Navigation | Selenium + type keyword into `#search` box + switch tabs + download to `tempfolder`, ~20 s of `sleep()` per list | same | plain `requests` against the JSON API, no browser, ~30 s for all five lists |
| `RegCode` | `'CSRC'` — **wrong regulator** (`reg.split()[1]` off a key literally named `CN CSRC 1`) | `'CSRC'` — same bug | `'NFRA'` |
| Schema | **44 keys** — an extra `'Check'` key not in the house schema | 44 keys, same extra `'Check'` | **exactly 43 keys**, asserted at import |
| `Name` | English name; falls back to a *live Google Translate call* on `无` | Chinese name in `Name`, English (or a machine translation) in **`Name - Mother Company`** — that field means the *parent company*, so every row asserted a false parent | English official name, falling back to the Chinese legal name; **no `Name - Mother Company`** is written |
| Translation | `googletrans` at scrape time — non-deterministic, rate-limited, silently falls back to the raw Chinese in v2 | same | none — NFRA publishes its own official English column |
| Dedup | `df.drop_duplicates()` before save — would silently drop legitimately repeated rows | same | **no dedup**; row count matches the source exactly |
| Column sync | `bourange_same_length_array()` back-fills columns with `''` *after* the fact — a mis-sequenced append corrupts the row alignment and is never detected | same | single `add_row(**kw)` appends to all 43 keys per record; unknown key raises; column lengths asserted after every list |
| `ListLabel` / `ListLanguage` / `ListValidityDate` / `Cntry` / `CoType` | never populated | never populated | populated |
| Excel typing | none — `000001` and `G0001H...` at risk | none | ID/Zip/Phone forced to text + workbook read back and asserted |
| `'无' in ENname` bug | correct | **`if '无' or '' in ENname:`** — always truthy, so *every* row took the translation branch | n/a |
| Output path | absolute Windows path `C:\Users\wuj1\...` | same | `os.path.dirname(os.path.abspath(__file__))` with notebook fallback |

### `list3_ver5.txt` / `list3_ver5.xlx`

Both are **leftover manual debug dumps from v1/v2, not inputs** — nothing reads them.
`list3_ver5.txt` is a CSV (despite the `.txt` extension) written by the last cell of both
notebooks, `df.to_csv('list3_ver5.txt')`. It contains **239 rows of list 3 only**
(List of Insurance Institutions), with `RegCode=CSRC`, a 44th `Check` column, and
`ListProcessDate=2025-01-08`. `list3_ver5.xlx` (note the typo'd extension — it is not `.xlsx`)
is the same data. They exist because list 3 was being eyeballed by hand while the
translation branch was being debugged. **v3 does not read or write them**; they can be
deleted once the requester is happy.

---

## Field mapping (identical for all five lists — the PDFs share one schema)

Source header: `序号 | 中文全称 | 英文全称 | 机构编码 | 机构类型 | 监管责任单位`

| PDF column | → sqldict field | Note |
|---|---|---|
| 英文全称 (English full name) | `Name` | used when present |
| 中文全称 (Chinese full name) | `Name` | **fallback** only, when 英文全称 is blank / `无` |
| 机构编码 (institution code) | `InternalID_1` + `InternalID_1_type='Organization code'` | forced to text |
| 机构类型 (institution type) | `CoType` | e.g. 农村商业银行, 村镇银行, 保险集团（控股）公司 |
| 序号 (sequence no.) | *not stored* | used only for the reconciliation check |
| 监管责任单位 (responsible supervisor) | *not mapped* | **open judgment call** — see below |

Constants: `Cntry='CN'`, `RegCtry='CN'`, `RegCode='NFRA'`, `RegulationType='Regulated'`,
`ListProcessDate=<run date>`, `ListCode=<1..5>`, `ListName=<ticket English name>`.

`RegulationType='Regulated'` for all 3983 rows: all five are positive/authorised registers.
NFRA does publish revocation notices (撤销/注销) elsewhere on the site, but none of the five
lists on this ticket is a withdrawal register, so no other value is used.

### `ListLanguage` is per-row, not per-list

NFRA leaves 英文全称 blank for a large minority of the smaller banks. Observed on this run:
**`EN` 2920 rows / `ZH` 1063 rows.** Rows whose `Name` is the Chinese legal name are marked
`ZH`; rows carrying NFRA's own official English name are marked `EN`. A blanket `EN` would
have been false for a quarter of the file. All the `ZH` rows are in list 1 (village/rural banks
and rural credit cooperatives, which have no registered English name).

---

## Row-count reconciliation

Each PDF numbers its own rows in 序号, so the last 序号 on the last page **is** the regulator's
declared record count. The scraper compares them and prints a `[WARN] ROW COUNT MISMATCH` line
on any disagreement. Result of the 2026-08-20 run:

```
CN NFRA 1  List of Banking Financial Institutions        scraped=3619 declared=3619  OK
CN NFRA 2  List of Branches of Foreign Banks             scraped= 114 declared= 114  OK
CN NFRA 3  List of Insurance Institutions                scraped= 239 declared= 239  OK
CN NFRA 4  List of Foreign Reinsurance Company Branches  scraped=   8 declared=   8  OK
CN NFRA 5  List of Financial Holding Companies           scraped=   3 declared=   3  OK
TOTAL scraped = 3983
```

No deduplication is performed. If an entity appears more than once it is kept, because the
requester QAs by counting rows at the source.

---

## Site quirks that will break this scraper later

1. **`pageSize` is capped at 20 server-side.** `pageSize=200` returns 20 rows and a correct
   `total`. The discovery loop pages until the declared total is reached (`max_pages=10`).
   The five current lists happen to sit in the newest 20 documents, but do **not** assume that.
2. **Attachment filenames are random GUIDs under a year folder** (`/chinese/docfile/2026/<32 hex>.pdf`)
   and change at every republication. Never cache them.
3. **`pdfFileUrl` on the document record is a decoy.** `/chinese/OFFICE/PDF/<docId>.pdf` returns a
   valid but **empty 968-byte** PDF (1 page, no text, no table). The data is *only* in
   `attachmentInfoVOList`. A length check would not have caught this — a `%PDF` magic-byte check
   plus an actual table extraction is what catches it.
4. **`docClob` contains no table.** The article body is a Word-exported HTML stub; parsing it
   yields 0 tables for all five documents.
5. **Twice-yearly republication.** Documents seen: 截至2024年12月末 (published 2025-03-17),
   截至2025年6月末 (2025-10-09), 截至2025年12月末 (2026-08-14). The scraper always takes the
   newest by `publishDate`, so a rerun after the next release picks up the new file automatically —
   but `ListValidityDate` will move and row counts will shift.
6. **The numbering of the attachment titles is not the ListNr.** The reinsurance list is
   published as `5.外国再保险公司分公司名单...` and the holding-company list as
   `6.金融控股公司法人名单...`, while they are ListNr 4 and 5 on the ticket. Matching is done on
   the Chinese title keyword, never on that leading digit.
7. **Encoding.** The JSON API is UTF-8 and decodes cleanly, so there is no GB2312/GBK problem in
   practice — but `docClob` internally declares `charset=gb2312`, so if anyone ever switches to
   scraping the HTML body, decode `r.content` explicitly (`utf-8` then `gb18030`). The scraper's
   `get_json()` already does this. Verified: **0 mojibake rows** in the output.
8. **Wrapped cells contain hard newlines.** `英文全称` and `机构类型` routinely come back as
   `'Raiffeisen Bank International AG\nBeijing Branch'`. All cells are whitespace-collapsed.
9. **Corporate TLS proxy** — every request uses `verify=False` with warnings disabled.

### Volume note

The brief warned about NFRA's 金融许可证 (financial licence) register, which covers every bank
**branch** in China and runs to hundreds of thousands of records. **That register is a different
system (`https://xkz.nfra.gov.cn`) and is not in scope for this ticket.** All five lists here are
法人 / 分行 registers (legal persons and foreign bank branches), totalling 3983 rows. The full
run takes ~30 seconds. No volume problem.

---

## Judgment calls for the requester

1. **`ListLabel` for list 5 (Financial Holding Companies) — currently `4`.** These are
   non-operating holding companies above mixed banking/insurance groups. `3` (bank & insurance)
   is arguable if the label is meant to describe the *group's* activity rather than the entity's.
   Please confirm `4` vs `3`.
2. **`Name` language.** 1063 of 3619 banking rows have no official English name at NFRA, so
   `Name` is the Chinese legal name and `ListLanguage='ZH'` for those rows. v1/v2 machine-translated
   these with `googletrans`. v3 deliberately does not — a machine translation is not the entity's
   legal name and is not reproducible run to run. **Confirm this is preferred**, or say whether a
   translation pass should be added (the `regulator-translate` skill exists for this).
3. **`监管责任单位` (responsible supervisory unit) is currently dropped.** It names the local
   NFRA bureau, e.g. `北京金融监管局`, `上海金融监管局`, or `金融监管总局` for nationally
   supervised entities. It reliably encodes the entity's province/municipality and could populate
   `City`. It was **not** mapped because the supervising bureau's seat is not strictly the
   entity's own address, and writing a derived city into an address field risks wrong data.
   Say the word and it can be mapped to `City` (or to `License_Type`/`Typology`).
4. **No address, phone, website, LEI or licence number is available.** These PDFs carry only the
   six columns above. Those sqldict fields are intentionally blank.
5. **`RegulationDate = 2026-08-14`** is the *publication* date of the list, not each entity's own
   authorisation date (NFRA does not publish per-entity authorisation dates in these files).
   Confirm that is the intended semantics; `ListValidityDate = 2025-12-31` carries the as-of date.
6. **Lists 2 and 4 are branches of foreign institutions located in China.** `Cntry='CN'` is used
   (the branch is a Chinese establishment). If the requester wants the *parent's* country instead,
   that would need `Cntry - Mother company`, which is not derivable from these PDFs without
   parsing the Chinese name for a country prefix.
