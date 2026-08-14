# HK IAHK

## Regulator Information

- **Country/Region Code**: HK
- **Regulator Code**: IAHK
- **Full Name**: Insurance Authority (Hong Kong)
- **Website**: https://www.ia.org.hk/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6746

## Script

- **Current Version**: `HK_IAHK_v1_5.py` (supersedes `HK_IAHK_v1_4.py` →
  `HK_IAHK_v1_3.py` → `HK_IAHK_v1_2.ipynb`)
- **Approach**: a DrissionPage browser clears Cloudflare and **stays open** for
  the whole run; data comes from a JSON API for list 1 and two published `.xlsx`
  workbooks for lists 2 and 3. Reads go over plain `requests` while Cloudflare
  allows it, and fall back to fetching **inside the browser** the moment it does
  not. `verify=False` for the corporate TLS proxy.

### Why v1.5 exists — the production 503

The third production failure, same day. v1.4 got past the 403 **and** past
Cloudflare, read 111 insurer detail pages, and then died on the 112th:

```
RuntimeError: the browser itself got HTTP 503 for
    https://www.ia.org.hk/iareg/insurerdetail.php?lang=en&ubi_no=01989895
  File "...HK-IAHK.py", line 588, in <module>
    detail = channel.json(INSURERS_DETAIL_API.format(ubi)).get('data') or {}
```

**Measured on the live site, 2026-08-13, through the same browser channel:**

| check | result |
|---|---|
| `ubi_no=01989895` fetched on its own | HTTP **200** — "QBE Hongkong & Shanghai Insurance Limited" |
| its position in the loop | entry **112 of 162** |
| all 162 detail calls back to back, no pacing | **6.1 s, `{200: 162}`** — every one succeeded |

So the record is not broken and the request pattern is not inherently refused.
The production box met a **transient** refusal — one call in 162 came back 503.
Cloudflare returns 503 for a rate-limited or re-challenged sub-request, and that
box has already demonstrated it is challenged far harder than the dev Mac (it
produced both earlier failures).

**The defect is not the 503.** Over 162 requests a refusal is a matter of time,
and the site owes us nothing. The defect was v1.4's reaction:

- any non-200 was **fatal on the spot**, no retry, no backoff — one blip threw
  away a run that had already completed 111 detail pages;
- the refusal body was **discarded**, so the error could not distinguish
  "Cloudflare re-challenge" from "origin down" — different problems, different
  fixes;
- **one** unreadable insurer took the other 161 with it, even though the list
  API already carries that insurer's name, type, business nature and year.

**v1.5:**

- browser reads retry on transient statuses (`403/408/429/500/502/503/504` and a
  network-level XHR failure) up to **5 attempts**, backing off 3 → 6 → 12 → 24 s,
  and **re-clearing Cloudflare from attempt 2** in case it was a re-challenge;
- once anything has needed a retry, a **0.5 s inter-call throttle** switches on
  for the rest of the run — 162 calls in 6 s is precisely the traffic shape a
  rate limiter exists to stop;
- the failing body is **captured and quoted** in the error, and a challenge body
  is named as such;
- a non-retryable status (e.g. 404) is still refused immediately rather than
  being asked five times;
- if a detail page is *still* unreadable, that insurer is written **from the list
  API** rather than aborting: row count stays 162, the row's address/phone/fax/
  website/email are blank, and every such row is listed loudly at the end. Never
  silently dropped, never silently reported as complete.

The run also now prints `Browser-side reads that had to be retried: N`, so the
production log says whether the box is being throttled at all.

**Verified live, 2026-08-13:**

| run | transport | retries | rows |
|---|---|---|---|
| `HK_IAHK_v1_5.py` unmodified | `requests` | 0 | 162 / 1467 / 811 = **2440** |
| same script, fallback forced on | `browser` | 0 | 162 / 1467 / 811 = **2440** |

Both workbooks **identical in content** (`DataFrame.equals` → `True`, 2440 × 43).
The QBE row that 503'd in production carries its full address, phone and email.

The retry logic itself was unit-tested against a stub page returning scripted
statuses — four checks: one 503 then success (recovers on attempt 2); three
refusals in a row (recovers on attempt 4, Cloudflare re-cleared twice);
permanent 503 (gives up after exactly 5 calls with the body quoted); 404 (not
retried at all — 1 call).

**Not verified from here**: the 503 cannot be reproduced on the dev Mac, so
"Cloudflare rate limit / re-challenge on that egress IP" is the *likely* cause,
not a proven one. What is proven is that the URL and the loop are fine here, and
that v1.4 could not survive a single refusal. v1.5 removes that dependency
regardless of which upstream reason produced it.

### Why v1.4 exists — the production 403

The Windows production box (`C:\Users\LaraZenl\...`, Python 3.8) failed on
2026-08-13 with:

```
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
    https://www.ia.org.hk/iareg/insurerlist.php?lang=en
  File "...HK-IAHK.py", line 301, in <module>
    payload = get_json(session, INSURERS_LIST_API)
```

**The site did not change.** The same v1.3 code was re-measured on the dev Mac
the same day: `cf_clearance` issued, `requests` → **HTTP 200**, 71567 bytes of
JSON. So the fault is the transport, not the scraper.

v1.3's design was: open a browser, take the `cf_clearance` cookie, **close the
browser**, then do all 162 detail calls and both workbook downloads over plain
`requests`. That hand-off is the single point of failure. Cloudflare does not
treat `cf_clearance` as a bearer token — it re-checks the caller against the
client the cookie was issued to:

| checked | v1.3 carried it over? |
|---|---|
| User-Agent | yes — copied from `navigator.userAgent` |
| TLS handshake fingerprint | **no** — Python 3.8's requests/urllib3 does not hand shake like Chrome |
| egress IP | **no** — the browser and requests can leave through different proxy hops |

That is why one machine passes and another does not, with identical code.

**v1.4 stops depending on the hand-off:**

1. The browser stays open for the whole run.
2. `requests` is still tried first — when it is allowed it is fast (~0.7 s/call,
   measured), and today on the Mac the run still picks it.
3. The first time `requests` is refused, **every later call goes through the
   browser** — a synchronous `XMLHttpRequest` issued from the register page's
   own origin. It carries the Cloudflare cookie, the browser's TLS handshake and
   its exact headers, because it *is* the browser. Binary `.xlsx` payloads go
   through the same channel, base64-encoded back into Python.
4. The Cloudflare wait is a **poll** (90 s budget) instead of v1.3's flat
   `page.wait(5)`. A loaded box needs longer than five seconds, and v1.3 did not
   notice — it sailed past the interstitial and died 15 lines later on a bare
   403. Running out of patience is now an explicit, named failure.
5. If neither channel can read the register, the script stops **there**, naming
   the cause, rather than raising a raw `HTTPError` from inside a helper.

The transport actually used is printed at the start and again at the end of
every run, so the production log says which path it took.

### The second production failure — `ContextLostError`

The first v1.4 run on the Windows box **got past the 403** and then died inside
the new Cloudflare poll:

```
DrissionPage.errors.ContextLostError:
    The page is refreshed. Please wait until the page is refreshed or loaded.
    Version: 4.1.1.2
  File "...HK-IAHK.py", line 322, in load_and_clear
    if not looks_like_challenge(page.html) and 'just a moment' not in title.lower()
```

The interstitial **reloads itself while it works**, so the DOM root object id
DrissionPage is holding goes stale under the poll and `page.html` throws. This
is not a fault — it is what "the challenge is still running" looks like from
outside, and it confirms the box really was being challenged. The poll was
simply reading at the wrong instant.

Fixed by:

- `safe_html()` / `safe_title()` — every page read in the wait loop is guarded
  and a raise is treated as "not ready yet". Caught broadly on purpose:
  `ContextLostError`, `PageDisconnectedError` and `ElementLossError` all mean
  the same thing here and their names have moved between DrissionPage versions
  (production is **4.1.1.2**, the dev Mac **4.1.1.4**).
- `CLEARANCE_TIMEOUT` 90 → **120 s**.
- The browser channel **re-anchors once** if the origin page is lost mid-run,
  instead of taking all 162 remaining calls down with it.
- The timeout message now reports the last title and HTML size it saw, so the
  next failure names what it was stuck on.

**Verified live, 2026-08-13 — both paths, full runs:**

| run | transport | rows |
|---|---|---|
| `HK_IAHK_v1_4.py` unmodified | `requests` | 162 / 1467 / 811 = **2440** |
| same script, fallback forced on | `browser` | 162 / 1467 / 811 = **2440** |
| after the `ContextLostError` fix | `requests` | 162 / 1467 / 811 = **2440** |

The two transports' output workbooks are **identical in content**
(`DataFrame.equals` → `True` across all 2440 rows and all 43 columns), so the
fallback is not a degraded mode — it returns exactly the same data, only slower.

The `ContextLostError` guard was tested against a stub page that raises exactly
the way production did (five checks: unguarded read still raises; `safe_html`
→ `None`; `safe_title` → `''`; `load_and_clear` survives two refreshes plus a
challenge page and returns the real HTML; a page that never clears produces the
named timeout error rather than a later bare 403).

**Not verified from here**: Cloudflare clears itself in a few seconds on the dev
Mac, so the *interactive* "Verify you are human" checkbox variant cannot be
reproduced. If the production box is sitting on a checkbox that never ticks
itself, the 120 s poll will time out with the message above — that message is
the signal to look at the Chrome window, not evidence of a code fault.

Parsing, field mapping and counts are v1.3 unchanged. The script is Python 3.8
compatible (no f-strings, no walrus, no dict-union) for the production box.

### Why v1.3 exists

**v1.2 died before writing a single row.** It did

```python
driver.find_element(By.LINK_TEXT, 'Download Full List').click()
```

on the Register of Authorized Insurers page. **That link no longer exists** —
confirmed live 2026-08-13: the page now renders 22 alphabetical tables of
insurer names and has no download anchor at all. v1.2 raised
`NoSuchElementException` there.

The register is instead served by a JSON API that the page itself calls:

```
https://www.ia.org.hk/iareg/insurerlist.php?lang=en             -> 162 insurers
https://www.ia.org.hk/iareg/insurerdetail.php?lang=en&ubi_no=<id>
```

The detail endpoint carries every field the retired workbook had (address /
tel / fax / website / email / place of incorporation) **plus** the UBI number,
so nothing is lost by the change. The register page's 162 anchors were counted
against the API's 162 rows as a cross-check.

### Cloudflare

`www.ia.org.hk` sits behind Cloudflare. Plain `requests` with no cookie gets
**403 "Just a moment…"** on both the HTML pages and the `.php` endpoints
(re-measured 2026-08-13), and headless Chrome is challenged and never clears.

v1.4 opens **one non-headless DrissionPage browser**, waits for the challenge to
actually release, and keeps it open as the fallback transport for the rest of
the run. See "Why v1.4 exists" above for why the cookie alone is not enough on
every machine.

> `options.headless(False)` is **deliberate** and must not be "optimised" away.
> Neither may the browser be closed early — it is the fallback transport.

Other v1.3 changes (all carried into v1.4):

- **pandas 2.x** — v1.2 ended with `writer.save()`, removed in pandas 2.0
  (`AttributeError: 'OpenpyxlWriter' object has no attribute 'save'`). v1.3 uses
  `df.to_excel(path, sheet_name='SQL Ready')` and writes into the **regulator
  folder**, not `tempfolder`.
- `scriptfolder` resolved per project convention — v1.2 hard-coded
  `C:\Users\wuj1\OneDrive - moodys.com\...`, the retired tenant.
- **Per-row padding.** v1.2 called `bourange_same_length_array()` once per
  *list*; v1.3 pads after every row, so a missing email/fax cannot shift a column.
- **Licence status is honoured.** v1.2 stamped every intermediary `Regulated`;
  the workbooks in fact carry `Active - Suspended` and
  `Active - Suspended (No RO)` rows, which v1.3 reports as `Suspended`.
- **`ISO_HK` extended to 44 entries**, matched case-insensitively. The API
  returns place of incorporation in UPPER CASE with names v1.2's map lacked
  (`GERMANY`, not "Federal Republic of Germany"; `THE PEOPLE'S REPUBLIC OF
  CHINA`; `UNITED STATES OF AMERICA`; `SWEDEN`). Any unmapped value is printed
  as a loud warning instead of silently becoming `None`.
- Non-schema `'Check'` column dropped from `sqldict`.
- New data captured that v1.2 dropped: UBI number → `InternalID_1`, insurer type
  → `CoType`, business nature → `License_Type`, year of first authorization →
  `RegulationDate`.

## List Types

`ListLabel` left blank — all three lists are pre-existing and colleagues fill the
label manually downstream (user decision, 2026-08-13). No new list was added.

| ListNr | ListName | ListLabel | Source |
|--------|----------|-----------|--------|
| 1 | Register of Authorized Insurers | *(blank)* | `iareg/insurerlist.php` + `iareg/insurerdetail.php` |
| 2 | List of Licensed Insurance Agencies | *(blank)* | `Download Full List – Licensed Insurance Agencies` → `files/LALIA_<date>.xlsx` |
| 3 | List of Licensed Insurance Broker Companies | *(blank)* | `Download Full List – Licensed Insurance Broker Companies` → `files/LALBC_<date>.xlsx` |

The two workbook links are discovered by their **anchor text**, so the dated
filename (`LALIA_31July2026.xlsx` at time of writing) does not have to be
hard-coded and the script keeps working after the monthly republication.

## Field mapping

### List 1 — authorized insurers (JSON)

| sqldict field | Source |
|---------------|--------|
| Name | `en_name` (detail, falling back to the list payload) |
| InternalID_1 / _type | `ubi_no` / `Unique Business Identifier` |
| CoType | `en_insurer_type` |
| License_Type | `en_business_nature` |
| Address_1 | `en_address` |
| Cntry | `en_poi` (place of incorporation) → ISO via `ISO_HK` |
| Phone / Fax / Website / Email | `tel` / `fax` / `website` / `email` |
| RegulationDate | `auth_year` — year of first authorization |
| RegulationType | `Regulated` |

### Lists 2 and 3 — intermediaries (workbooks)

| sqldict field | Source |
|---------------|--------|
| Name | licensee name column |
| InternalID_1 / _type | licence number / `Licence No.` |
| License_Type | line of business, English part only (the cell holds `English / 繁體 / 简体`) |
| RegulationType | `Active` → `Regulated`; anything containing "suspend" → `Suspended` |

### All lists

`RegCtry` = `HK`, `RegCode` = `IAHK`, `ListLanguage` = `EN` (the registers are
published EN/TC/SC; every field taken here is the English one),
`ListProcessDate` = run date (`%Y-%m-%d`).

## Status / QA

- **Output**: `HK IAHK SQL Ready 2026-08-13 17.40.46.xlsx`, **2440 rows**,
  fixed 43-column schema, sheet `SQL Ready`. Reproduced on v1.5 once per
  transport, with identical content (and on v1.4 before it — the row count has
  not moved across any of the three fixes).

| ListNr | ListName | RegulationType | rows |
|--------|----------|----------------|------|
| 1 | Register of Authorized Insurers | Regulated | 162 |
| 2 | List of Licensed Insurance Agencies | Regulated | 1453 |
| 2 | List of Licensed Insurance Agencies | Suspended | 14 |
| 3 | List of Licensed Insurance Broker Companies | Regulated | 807 |
| 3 | List of Licensed Insurance Broker Companies | Suspended | 4 |
| | **Total** | | **2440** |

- List 1: the register page has exactly **162 anchors** and the API returns
  exactly **162 rows** — independent confirmation that nothing is paginated away.
- Lists 2 / 3 match their workbooks exactly: 1467 and 811 rows.
- **v1.2's last good run had 158 / 1569 / 800.** The agency count really did
  fall — the workbook itself has 1467 rows; this is not a scraping loss.
- List 1 fill rates: Name 162/162, InternalID_1 162/162, License_Type 162/162,
  Cntry 162/162, RegulationDate 162/162, Address_1 160/162, Phone 160/162,
  Email 149/162, Website 138/162, CoType 53/162.
- `RegulationType` and `ListProcessDate` non-empty on all 2440 rows; schema is an
  exact match for CLAUDE.md with no `Check` column.
- **3 duplicate (Name, ListCode) pairs are genuine** — the same trading name
  holding two distinct licence numbers. Deliberately kept, per the standing rule
  that the output row count must match what a human counts on the site.
- Every place-of-incorporation value mapped; `unmapped_countries` was empty.
- `Browser-side reads that had to be retried: 0` on both v1.5 runs, and no
  degraded rows — nothing refused us from here.

### Items needing your confirmation

1. **`Cntry` on list 1 is the place of *incorporation*, while `Address_1` is the
   Hong Kong office address.** So a Bermuda-incorporated insurer shows
   `Cntry = BM` next to a Hong Kong street address. Confirm this is what BVD
   wants, or say the word and I will set `Cntry = HK` and move the place of
   incorporation elsewhere.
2. **United Kingdom is mapped to `UK`, not `GB`.** That follows v1.2's map.
   ISO 3166-1 alpha-2 is `GB` — tell me which BVD expects.
3. **Three insurers carry liquidation / winding-up dates** and are currently
   written as `Regulated` with an empty `CancellationDate`:
   - FAI First Pacific Insurance — 2001-04-09
   - HIH Casualty and General Insurance (Asia) — 2001-04-09
   - Target Insurance Company — 2022-09-26

   They are still on the register, which is why they are included. Confirm
   whether they should instead get `RegulationType = 'In Liquidation'` and the
   date in `CancellationDate`.

### Environment notes

- Requires **DrissionPage** and a real (non-headless) Chrome. A browser window
  opens at the start of the run and stays open until the last row is read — it
  is the fallback transport, so do not close it. On a headless server this
  script will fail at the Cloudflare step, by design and with a clear message.
- **Python 3.8 compatible** (the production box runs 3.8): no f-strings, no
  walrus operator, no dict-union.
- If the run logs `requests was refused (...)  Switching to browser-side
  fetching`, that is the fix doing its job, not a fault. It is slower —
  the browser channel is a synchronous XHR per call — but the output is
  identical.
- Otherwise global Python environment: `requests`, `beautifulsoup4`, `pandas`,
  `openpyxl`.
- `verify=False` + `urllib3.disable_warnings` are required behind the corporate
  TLS proxy.
