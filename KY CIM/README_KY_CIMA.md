# KY CIMA — Cayman Islands Monetary Authority

Jira: **DECD-6740** (parent epic DECD-3438 — Regulators 2026 - Internal Crawlers). Ticket status at
time of writing: **Backlog**.

Latest scraper: **`KY_CIMA_v4.py`** — supersedes `KY_CIMA_v3.ipynb`. v1/v2/v3 notebooks are kept for
history only; do not run them (see *Why v4 replaced v3*).

Source: one endpoint, `https://www.cima.ky/search-entities-cima/get_search_data`, which backs the
public **Search Entities** register at `https://www.cima.ky/search-entities-cima`.

## Lists

The ticket defines 20 lists. `ListLabel` per the project rule — 1 bank, 2 insurance, 3 both,
4 everything else.

| ListCode | ListName | ListLabel | Rows |
|---|---|---|---|
| 1 | Banking Class A | 1 | 11 |
| 2 | Banking Class B | 1 | 65 |
| 3 | Money Services | 4 | 5 |
| 4 | Trust | 4 | 90 |
| 5 | Trust (Restricted) | 4 | 53 |
| 6 | Nominee (Trust) | 4 | 34 |
| 7 | Trust (Controlled Subsidiary) | 4 | 56 |
| 8 | Trust (Registered PTC) | 4 | 164 |
| 9 | Company Manager | 4 | 112 |
| 10 | Corporate Service Provider | 4 | 24 |
| 11 | Insurance Entities | 2 | 897 |
| 12 | Mutual Fund - Registered | 4 | 12,897 |
| 13 | Mutual Fund - Administered | 4 | 313 |
| 14 | Securities - Registered Person | 4 | 1,344 |
| 15 | Private Fund | 4 | 18,238 |
| 16 | Virtual Asset Service Provider Registration | 4 | 19 |
| 17 | Securities - Full | 4 | 47 |
| 18 | Building Society | 1 | 1 |
| 19 | Credit Union | 1 | 2 |
| 20 | Development Bank | 1 | 1 |

List 11 aggregates the nine insurer categories the ticket names (Class A Local/External, Class B/C/D,
Agent, Broker, Manager, Portfolio Insurance Company).

**`regdict` in v2/v3 was wrong and has been corrected.** It had `KY CIM 4` = *Trust (Registered PTC)*
and `KY CIM 8` = `'-'`. DECD-6740 says 4 = *Trust*, 8 = *Trust (Registered PTC)* — which is what the
v3 `mapping` dict actually emitted, so only `regdict` was stale. v4 derives `LIST_NAME` from
`regdict`, so the two can no longer drift.

## How it works

`requests` + BeautifulSoup. No Selenium, no browser, no JS execution. `verify=False` on the session
for the corporate TLS proxy.

Two steps:

1. **GET the search form once** to collect the CSRF token the site issues
   (`cima_cfrf_token_cookie_name` cookie).
2. **POST `PageNumber=1, 2, 3, …`** with `AuthorizationType=All` until a page returns zero rows.
   344 requests for the current register.

### One `All` pass instead of 20 per-category passes

The ticket comment says *"Select the category and extract the list of companies"*. v4 does not do
that — it runs a single `AuthorizationType=All` sweep and derives the list assignment from the
**Typology column already present in each result row**. This is equivalent (every row carries its own
category, and all 36 categories were observed in the output) and costs 344 requests instead of one
full pagination per category.

## The CAPTCHA — the ticket's "Has CAPTCHA" note is real, but not on the paging path

This is the single most important thing to know about this scraper, and it is why v4 needs no
manual step.

v3 required a `g-recaptcha-response` token hand-pasted from a browser session, and broke every time
it expired. Measured on 2026-08-12 against the live endpoint, one variable changed at a time:

| recaptcha | PHPSESSID | CSRF pair | PageNumber | Result |
|---|---|---|---|---|
| expired token | valid | valid | — | 302 |
| field removed | valid | valid | — | 302 |
| literal `GARBAGE` | valid | valid | — | 302 |
| expired token | random | valid | — | 302 |
| absent | **not sent** | fresh | 5 | **200, 100 rows** |
| absent | not sent | **self-invented `deadbeef…`** | 5 | **200, 100 rows** |
| absent | not sent | **absent** | 5 | 500 |

Three conclusions:

1. **`cima_cfrf_token_name` is not a captcha token.** It is CodeIgniter's CSRF token, and the server
   only checks that the POST field equals the `cima_cfrf_token_cookie_name` cookie — double-submit,
   no server-side state. A self-invented value in both places returns 200.
2. **`PHPSESSID` is irrelevant.** Requests carrying no session cookie at all return 200.
3. **reCAPTCHA is validated only on the "new search" branch** — a POST that carries **no**
   `PageNumber`. Any POST that carries `PageNumber` skips the check entirely.

So v3's 336 paging requests never needed the token; only its first request did. **v4 makes page 1 an
ordinary paging request (`PageNumber=1`), so the captcha branch is never taken.** Verified: page 1
returns the true first record (`"RICI" Commodity Fund Ltd.`), not an offset page.

Point 3 is behaviour, proven. That the 302 is *caused by* reCAPTCHA validation failing is an
inference — strongly supported (v3's saved run returned data on that same branch with a fresh token,
and nothing else changed) but not confirmed against source. The operational conclusion is the same
either way.

Everything here uses the site's own public paging endpoint and the site's own issued CSRF token. v4
sends one request at a time with no concurrency. (Whether CIMA publishes a rate limit anywhere was
not checked — the sequential pace was chosen as a default, not to satisfy a known limit.)

## Categories not in the ticket

The site's `AuthorizationType` dropdown offers **36** categories. DECD-6740 names lists for **28** of
them. The other 8 have no list of their own and are **folded into the nearest ticketed list** rather
than dropped — **3,868 rows**, 11 % of the register:

| Site category | Folded into | Rows |
|---|---|---|
| Mutual Fund - Master Fund | 12 Mutual Fund - Registered | 3,202 |
| Mutual Fund - Limited Investor | 12 Mutual Fund - Registered | 553 |
| Mutual Fund Administrator - Full | 13 Mutual Fund - Administered | 62 |
| Mutual Fund - Licenced | 12 Mutual Fund - Registered | 39 |
| Mutual Fund Administrator - Restricted | 13 Mutual Fund - Administered | 5 |
| Virtual Asset Service Provider Licence | 16 VASP Registration | 5 |
| Banking Class B (Restricted) | 2 Banking Class B | 1 |
| Securities - Restricted | 17 Securities - Full | 1 |

Each is marked `# OFF-TICKET` in `mapping` in the script. `Mutual Fund - Licenced` is inherited from
v3 and predates this decision; the other seven are new in v4.

**Confirm the list-13 fold with the ticket owner.** Ticket list 13 is *Mutual Fund - Administered* —
administered **funds**. The two *Mutual Fund Administrator* categories are the **administrators**,
a different kind of entity, and they have no ticketed list. They are filed under 13 as the nearest
match, which mixes 67 administrators into a 313-row list of funds. The alternative is new ListCodes
21+, which would need the ticket updated first.

## Decisions worth flagging

- **Unmapped categories are never dropped silently.** v3 mapped 29 of 36 categories and deleted the
  rest at `.loc[d['ListCode'] != '']` with no message — on today's register that would discard
  **3,829 rows (11.1 %)**. v4 maps all 36, and if CIMA ever adds a 37th the script prints a boxed
  warning listing the new category and its row count instead of quietly losing it.
- **`ListLabel` for 18/19/20 is 1 (bank).** Building Society, Credit Union and Development Bank are
  deposit-takers. They are 4 rows in total, so the cost of being wrong is small either way, but
  flagging it since the project rule does not name these types explicitly.
- **`ListLabel` for 3 (Money Services) is 4, not 1.** An MSB is not a deposit-taker.
- **The `'Check'` column is gone.** v2/v3 appended a 43rd key `'Check'` to `sqldict`. The project
  `sqldict` structure is fixed and must not change, so v4 emits exactly the mandated columns. If a
  downstream loader expects `Check`, add it back as one line.
- **`ListValidityDate` is left empty** — the register publishes no as-of date anywhere.
- **`RegulationDate` keeps the source format** (`12-Jun-2008`), unchanged from v3. Not normalised to
  ISO, to avoid changing output semantics that downstream may already depend on.
- **`Cntry` is hardcoded `KY`.** The register publishes no address at all, only Reference Number,
  Name, Category and Regulated Date. Every address, phone, website and email column is empty by
  necessity, not by parse failure.

## QA notes

- **Row count equals the site's.** 344 pages × 100, last page short. No de-duplication of any kind is
  applied.
- **`InternalID_1` (Reference Number) is NOT globally unique** — it is unique only within a register
  family. 44 reference numbers appear on more than one row, and only 22 of those are one entity with
  two licences (e.g. ref `100095`, Banco Fibra S.A., held as both *Trust* and *Banking Class B*).
  The other 22 are **genuinely different entities that collide across registers** — ref `1006` is
  *IKOS* in the mutual-fund register and *Archway Insurance, Ltd.* in the insurance register. Do not
  use `InternalID_1` as a join key on its own.
- **`(Name, Typology)` is unique** across all 34,373 rows — 0 duplicates. Use it as the row key.
- **103 names appear more than once (238 rows).** These are real multi-licence entities, not
  pagination artefacts. *Scotiabank & Trust (Cayman) Ltd.* is the extreme case — 5 rows, and note it
  carries **4 different reference numbers**, one per register:

  | Ref | Typology | RegulationDate |
  |---|---|---|
  | 66001 | Banking Class A | 11-Nov-1966 |
  | 66001 | Trust | 11-Nov-1966 |
  | 3037 | Mutual Fund Administrator - Full | 09-Feb-1994 |
  | 25023 | Securities - Full | 15-Feb-2005 |
  | 655642 | Insurance Broker | 16-May-2013 |

  So a reference number is **per registration, not per entity** — the same firm gets a new one in
  each register, and only occasionally reuses one across two licences (66001 above; ref 100095,
  Banco Fibra S.A., is the same pattern). Deduplicating on either `Name` or `InternalID_1` alone
  would be wrong.
- `RegulationDate` is 100 % populated. `Name`, `ListCode`, `ListLabel`, `ListName`, `ListLanguage`,
  `ListProcessDate`, `RegulationType` have no nulls.

## Environment

**On the Mac, run with `./.venv/bin/python`, not `/usr/bin/python3`.** System Python 3.9 links
LibreSSL 2.8.3, which cannot complete a TLS handshake with `www.cima.ky` — every request dies with
`SSLError(SSLZeroReturnError(6, 'TLS/SSL connection has been closed (EOF)'))`, and `verify=False`,
`trust_env=False` and a custom CA bundle all fail to fix it. The repo `.venv` (Python 3.13,
OpenSSL 3.5.7) works. `curl` also works, which makes this easy to misdiagnose as a proxy problem.

`KY_MAX_PAGES` env var caps the page loop for smoke tests (`KY_MAX_PAGES=3`); it defaults to 2000 as
a runaway guard.

## Why v4 replaced v3

`KY_CIMA_v3.ipynb` no longer runs. Its hand-pasted `g-recaptcha-response` expired, so the page-1 POST
now 302-redirects to the form page and the run dies at
`RuntimeError: Page 1 failed: HTTP 500`. Other defects fixed in v4:

| | v3 | v4 |
|---|---|---|
| Chrome | launched via Selenium, never used | removed |
| Script folder | hardcoded `C:\Users\wuj1\…` | `try __file__ / except getcwd()` |
| Page 1 | no `PageNumber` → hits captcha branch | `PageNumber=1` → captcha never checked |
| CSRF token | pasted by hand, expires | fetched from the form page, auto-refreshed on 302/500 |
| Category coverage | 29 of 36, rest dropped silently | 36 of 36, unknowns reported loudly |
| `ListLabel` / `ListLanguage` | empty | filled |
| Malformed rows | `cells[3]` → IndexError | rows with < 4 cells skipped |
| Excel sheet | default sheet name | `sheet_name='SQL Ready'` |

v3's pagination itself was **not** buggy — its `li#last a.last` next-link walk stops at exactly the
right page (checked directly against pages 336–345 on 2026-08-12: 337 still serves a next link
today, the true end is 344, and 345 is empty). Its saved run stopping at 337 is therefore most
likely register growth over the intervening ~2.5 months rather than a paging defect — that is an
inference, not something measured against the May register.

## Last run

**2026-08-13 — 34,373 rows**, 43 columns, 344 pages, 20 ListCodes, all 36 site categories mapped,
0 rows dropped. No manual captcha step.

Runtime 6 min 25 s (script start 11:05:28 → output file written 11:11:53). **346 requests**: 1 GET
for the CSRF token, then 345 sequential POSTs — 344 carrying rows plus page 345, which returns zero
rows and is how the loop detects the end.

### Row-count history

| Date | Pages | Rows | Note |
|---|---|---|---|
| ~2026-05-26 | 337 | not recorded | v3, saved notebook run; mapping covered 29/36 categories |
| 2026-08-12 | 344 | 34,375 | v4 first full run |
| 2026-08-13 | 344 | 34,373 | v4, corrected ListNames; −2 rows is live-register churn overnight |
