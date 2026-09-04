# AL AFSA — Autoriteti i Mbikëqyrjes Financiare (Albanian Financial Supervisory Authority)

Jira: **DECD-6833**
Site: https://amf.gov.al (Albanian, `lang="sq-AL"`)
Scraper: `AL_AFSA_v3.py` / `AL_AFSA_v3.ipynb`
Run observed: 2026-08-20 — **46 rows total**, output `AL AFSA SQL Ready 2026-08-20 19.01.08.xlsx`

AFSA (AMF) supervises **insurance, private/supplementary pensions and securities markets**.
Banks are supervised by the Bank of Albania, not by AFSA — several banks appear in lists 3
and 7, but they appear there in their *investment-services* / *depositary* capacity, not as
licensed banks.

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows (observed) |
|---|---|---|---|---|---|---|
| 1 | 1 | 2 | List of "Insurance Companies" | https://amf.gov.al/ts_shoqeri_sigurimi.asp | static HTML accordion | 13 |
| 2 | 2 | 2 | List of "Reinsurance Companies" | https://amf.gov.al/ts_shoqeri_risigurimi.asp | static HTML accordion | 1 |
| 3 | 3 | 4 | List of "Brokerage Companies" | https://amf.gov.al/tt_shoqeri_komisionere.asp | static HTML accordion | 11 |
| 4 | 4 | 4 | List of "Registrars" | https://amf.gov.al/tt_rregjistrar.asp | static HTML accordion | 1 |
| 5 | 5 | 4 | List of "Regulated Markets" | https://amf.gov.al/tt_treg.asp | static HTML accordion | 1 |
| 6 | 6 | 4 | List of "Investment Funds" | https://amf.gov.al/tsik_fond.asp | static HTML accordion (free-text body) | 15 |
| 7 | 7 | 4 | List of "Depository for Collective Investment Undertakings" | https://amf.gov.al/tsik_depositare.asp | static HTML accordion | 4 |
| | | | | | **TOTAL** | **46** |

All seven ticket URLs are **still live** — each returned HTTP 200 and a populated
`div.panel-group` accordion on 2026-08-20. **No re-platform was found.**

### ListLabel justification (1 = bank, 2 = insurance, 3 = both, 4 = other)

- **List 1 = 2** — insurance undertakings (life and non-life), squarely insurance.
- **List 2 = 2** — reinsurance undertakings; the single entry (SIGAL INSURANCE GROUP sh.a.)
  is an insurer holding a reinsurance licence.
- **List 3 = 4** — investment-service firms under the securities law. 10 of the 11 entries
  are banks *by corporate form*, but the register is a securities-brokerage register, not a
  banking register; AFSA has no banking remit. `1` would misrepresent the list.
- **List 4 = 4** — securities registrar / central securities depository.
- **List 5 = 4** — regulated market (the Albanian Securities Exchange, ALSE).
- **List 6 = 4** — collective investment undertakings (funds, not institutions).
- **List 7 = 4** — depositaries for CIUs; again banks acting in a securities role.

`RegulationType = 'Regulated'` on all 46 rows: every one of these seven pages is a positive
register of currently licensed entities. AFSA publishes revoked/licence-withdrawn entries on
separate pages that are **not** in scope for this ticket.

---

## Site mechanics and quirks

**No browser is required to *parse*, but one is required to *fetch* on some boxes.**
Each page is a classic ASP page that renders a Bootstrap 3 accordion
(`div.panel-group` > `div.panel.panel-default`). The panel *bodies* — including every
address, phone and licence line — are present in the initial HTML response, so no clicking
is needed to expand panels (v2 drove DrissionPage and clicked each `h4`; that part is
genuinely unnecessary). **But see "Cloudflare blocks the control server" below: v3.0's
switch to pure `requests` is what broke the production run, and v3.1 restores a browser
fallback for the fetch only.**

### Cloudflare blocks the control server (fixed in v3.1)

`amf.gov.al` is behind Cloudflare. The 2026-08-25 production run died on the first list:

```
File ".../AL-AFSA/AL-AFSA.py", line 260, in <module>   soup = get_soup(url)
File ".../AL-AFSA/AL-AFSA.py", line 137, in get_soup   resp.raise_for_status()
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
    https://amf.gov.al/ts_shoqeri_sigurimi.asp
```

The same URL returned HTTP 200 from the dev Mac the same day. **Header tuning does not fix
this** — measured on the dev Mac, bare / Mac-UA / Windows-UA / full-browser-headers all
returned 200, so the refusal keys on the *client* (egress IP + TLS fingerprint), not on
what is sent. This is the same "works on the Mac, 403s on the control server" split that
HK IAHK hit.

v3.1 therefore uses a `Channel` that tries `requests` first and, the moment it is refused
(non-200, or a 200 carrying a challenge page), switches to a real Chrome via DrissionPage
for the rest of the run. The switch is sticky and one-way — if Cloudflare has decided this
client is unwelcome over `requests`, retrying it on all seven lists just costs seven more
refusals. `DrissionPage` is imported **lazily**, so a box where `requests` already works
never needs it installed.

`options.headless(False)` must stay: Cloudflare challenges headless Chrome and it never
clears. On a box that shows an "I am not a robot" checkbox, it must be ticked by hand once,
or `CLEARANCE_TIMEOUT` (120 s) raised.

Verified 2026-08-25 on the dev Mac by forcing the fallback: `requests` and the browser both
returned **13 panels** for list 1, with identical names and diacritics intact
(`ATLANTIK - SHOQËRI SIGURIMESH sh.a.`). **Not verified from the control server** — the 403
only reproduces from that box.

**Cloudflare e-mail obfuscation.** Every `mailto:` is replaced by
`<span class="__cf_email__" data-cfemail="...">[email protected]</span>`. Reading the visible
text yields the literal string `[email protected]` for every entity — which is what v2 would
have stored. v3 decodes the hex (`XOR` with the first byte) before reading panel text.
This produced 28 real **e-mail** addresses out of 46 rows. (Not to be confused with
`Address_1`, the postal address, which is filled on 31 of 46 — see "List 6" below.)

**Albanian diacritics.** Labels contain `ë`/`ç` (`Adresa e Selisë`, `Lloji i Pronësisë`,
`Fusha e Aktivitetit`) and AFSA's editors are not consistent about them. All label matching
goes through `norm()` — NFKD, combining marks stripped, whitespace collapsed, lower-cased —
and uses **substring** matching, never `==`. Stored *values* keep their diacritics (NFKC).

**Non-breaking spaces** (`\xa0`) appear throughout panel text and are normalised out.

**List 6 has a different shape.** Investment-fund panels carry **no** `li` label/value rows
at all — only an `h4` with the fund name and a `panel-body` sentence of the form
`NËN ADMINISTRIMIN E <management company>. DEPOZITAR I FONDIT: <depositary bank>`.
Consequently funds have no address, phone, e-mail, licence number or licence date. That is a
property of the source, not a scrape failure: 15 of the 16 empty `InternalID_1` values and
all 15 empty `Address_1` values come from list 6.

**Anti-brittleness.** No download filenames, file URLs or category enumerations are
hard-coded — the seven register URLs come from the ticket, and the number of panels on each
is discovered per run. `get_soup()` raises a loud
`SKIPPED - no accordion panels found at <url>` rather than silently returning 0 rows, so a
soft-404 or a proxy error page cannot masquerade as an empty register. Response length is
never used as a liveness signal.

---

## Field mapping

Applies to lists 1, 2, 3, 4, 5, 7 (the panels with label/value rows):

| Source label (Albanian) | sqldict key | Notes |
|---|---|---|
| `h4` panel heading | `Name` | |
| `Lloji i Pronësisë` | `CoType` | ownership type, e.g. *Shoqëri me kapital vendas* |
| `Fusha e Aktivitetit` | `License_Type` | scope of authorised activity |
| `Adresa e Selisë` | `Address_1` | registered-office address |
| (derived from address) | `City` | see judgment call below |
| `Tel./Faks` | `Phone` | see judgment call below |
| `Faqja e Internetit` | `Website` | |
| `Posta Elektronike` | `Email` | Cloudflare-decoded |
| `Licenca` or `Dt. e fillimit të Aktivitetit` | `InternalID_1` (+ `_type` = `License Number`) and `RegulationDate` | parsed by `parse_license()` |

List 6 (Investment Funds):

| Source | sqldict key |
|---|---|
| `h4` fund name | `Name` |
| `panel-body` full sentence | `License_Type` |
| text after `NËN ADMINISTRIMIN E` | `Name - Mother Company` |

Constants on every row: `RegCtry='AL'`, `RegCode='AFSA'`, `Cntry='AL'`,
`ListLanguage='SQ'` (the Albanian pages are what was parsed — no EN claim),
`RegulationType='Regulated'`, `Typology = ListName`, `ListProcessDate = %Y-%m-%d`.

`parse_license()` handles all three live phrasings —
`Nr. 5, datë 31.01.2022 (pa afat). Kjo Licencë zëvendëson ...`,
`Vendim Nr. 03, dt. 08.06.2000`, and `nr. 1 datë 13.12.2011 (pa afat)` — extracting the
number and converting `dd.mm.yyyy` to `YYYY-MM-DD`.

---

## Row-count reconciliation

The source does **not** print a declared total anywhere on these pages, so the only
authoritative count is the number of accordion panels rendered. The scraper counts panels
and compares them to rows stored, printing a `[WARN]` on any mismatch.

Observed on the executed run — **every list matched exactly, 46/46, zero warnings**:

```
AL AFSA 1 (Insurance Companies):     13 rows  = 13 panels
AL AFSA 2 (Reinsurance Companies):    1 row   =  1 panel
AL AFSA 3 (Brokerage Companies):     11 rows  = 11 panels
AL AFSA 4 (Registrars):               1 row   =  1 panel
AL AFSA 5 (Regulated Markets):        1 row   =  1 panel
AL AFSA 6 (Investment Funds):        15 rows  = 15 panels
AL AFSA 7 (Depositories):             4 rows  =  4 panels
TOTAL: 46
```

**No `drop_duplicates()` is used anywhere.** Legitimate cross-list repetition is preserved:
SIGAL INSURANCE GROUP sh.a. appears in both list 1 and list 2 (it holds both an insurance and
a reinsurance licence); BANKA E PARË E INVESTIMEVE, BANKA AMERIKANE E INVESTIMEVE,
BANKA E TIRANËS and BANKA CREDINS each appear in both list 3 and list 7. Within list 6,
RAIFFEISEN INVEST administers five separate funds — five distinct funds, five rows.

---

## What was wrong with v1 / v2

Both old notebooks were audited before v3 was written.

- **`RegCode` was CORRECT.** Both compute `reg.split(' ')[1]` over keys of the form
  `'AL AFSA 1'`, which yields `'AFSA'`. The copy-paste hazard that produced `RegCode='CSRC'`
  in CN NFRA did **not** occur here. v3 keeps the same derivation and the run confirmed
  `RegCode` is `['AFSA']` for all 46 rows.
- **Schema violation: both v1 and v2 declared 44 keys, not 43** — an extra trailing
  `'Check': []`. Every diff against the fixed schema shows exactly one extra key and zero
  missing keys. This alone would fail QA. Removed in v3, which asserts `len(SQL_KEYS)==43`
  at import time and re-asserts column order and count immediately before and after
  `to_excel`.
- **Hard-coded Windows path**:
  `scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"`
  with the portable `os.path.dirname(os.path.abspath(__file__))` line commented out. This
  cannot run on the control server. v3 uses the `try/except NameError` house pattern.
- **Selenium / `webdriver_manager` / ChromeDriver imports** (`from selenium import webdriver`,
  `from webdriver_manager.chrome import ChromeDriverManager`) plus a live
  `ChromiumPage` browser session. The control server has no browser driver. All removed —
  v3 is pure `requests`.
- **Wrong output location**: `df.to_excel(filename, index=False)` with no `sheet_name` and
  relying on an earlier `os.chdir`. v3 writes an explicit
  `os.path.join(scriptfolder, filename)` with `sheet_name='SQL Ready'`.
- **`[email protected]` for every entity** — v2 read `li` text directly without decoding
  `data-cfemail`, so no real e-mail address could ever have been captured.
- **Fragile click-to-expand loop** with `sleep(2)` per panel per entity (~46 panels × 4s),
  which is both slow and unnecessary since the bodies are in the initial HTML.
- No false `Name - Mother Company` was found in v1/v2, and no `drop_duplicates()` was
  present in either. The always-truthy-conditional pattern was not present either.

### What changed in v3

Pure `requests`+BeautifulSoup; 43-key schema enforced through a single `add_row()` that
appends to every key and raises `KeyError` on an unknown one; Cloudflare e-mail decoding;
accent-insensitive substring label matching; licence number/date parsing; per-list panel-vs-row
reconciliation printed to the log; ID/Zip/Phone columns forced to text before `to_excel` and
verified by reading the workbook back.

**Excel numeric coercion**: `InternalID_1`, `InternalID_2`, `InternalID_3`, `Zip`, `Phone`,
`Fax`, `Zip - Mother company`, `Phone - Mother company` are cast to `str` before saving, and
the script re-opens the saved workbook with `dtype=str` and asserts an ID round-trips as a
digit string (observed: `'3'`, type `str`).

### What changed in v3.1

Transport only — no parsing, mapping or schema change.

- `get_soup()` now fetches through a `Channel` that falls back from `requests` to a real
  Chrome on refusal (see "Cloudflare blocks the control server" above). This fixes the
  2026-08-25 production `403`.
- `HEADERS` swapped to a Windows Chrome UA (the control server is Windows) and given
  `Accept` / `Upgrade-Insecure-Requests`. This alone does **not** fix the 403 — it was
  measured as making no difference — but there is no reason to announce a Mac to a
  Windows-hosted run.
- The reconciliation block prints `transport used: requests|browser`, so the log says
  which path a given run actually took.
- Chrome is released via `channel.close()` as soon as the last page is read.

Re-run 2026-08-25 on the dev Mac: **46 rows, every list matching its source panel count**,
name set identical to the 2026-08-20 run (0 added, 0 dropped).

### What changed in v3.2

v3.1 cleared the `403` — the 2026-08-26 production run reached the site over the browser
(`transport=browser`) — and then died one step later:

```
RuntimeError: SKIPPED - no accordion panels found at
  https://amf.gov.al/ts_shoqeri_sigurimi.asp (len=632133, transport=browser)
```

**That was a bug in v3.1, not a site problem.** It used two different definitions of "this
is the page we asked for":

| | v3.1 test | verdict on a page with only `<style>.panel-default{}</style>` |
|---|---|---|
| browser wait-loop | substring `'panel-default'` or `'div class="panel'` | **accepted** |
| `get_soup()` assert | CSS selector `div.panel.panel-default` | rejected |

So the wait-loop handed back a page it should have kept waiting on, and the assert
reported it 15 lines later as a scrape failure. The substring test was far too loose
regardless: `div class="panel` also matches `panel-heading`, `panel-body` and
`panel-group` — 40 hits on a *good* page that has 13 real panels.

- **One acceptance test everywhere.** New `count_panels()` runs the CSS selector, and the
  requests path, the browser wait-loop and `get_soup()` all use it. Nothing that would
  fail the assert can now be returned as a success.
- **A 200 with no accordion falls back too.** A soft-404 or proxy interstitial over
  `requests` now gets one try through Chrome instead of killing the list outright.
- **The browser re-navigates** every ~20 s instead of only polling. Waiting lets a
  Cloudflare challenge clear, but it will never turn a *wrong* page into the right one.
- **Failures are kept, not guessed at.** `dump_failure()` writes the unusable HTML plus
  the URL the browser actually landed on to `tempfolder/FAILED <page> <timestamp>.html`.
  This box cannot reproduce the production failure, so the next one has to carry its own
  evidence.
- **Chrome is now isolated** — `auto_port(True)` plus `--disable-extensions`, so
  DrissionPage starts its own browser instead of attaching to whatever is already on
  `127.0.0.1:9222` with the operator's profile, extensions and any corporate
  content-injection agent. Verified locally: the test browser came up on port `48092`.
  Note `auto_port()` already allocates a throwaway user-data dir — calling
  `set_user_data_path()` as well sets `_auto_port = False` after the address has been
  blanked, and Chromium dies on `not enough values to unpack` before it starts. If the
  isolated launch fails, the code falls back to a shared Chrome and says so in the log.

**What the 632133-byte page actually was is still unknown.** This URL is ~125 KB with 13
panels here over both `requests` (126619) and Chrome's rendered DOM (124550), and the
homepage — 77775 bytes, no accordion — does not match either, so a redirect does not
explain it. A dirty shared Chrome profile is the leading suspect, which is why v3.2
isolates the browser, but **that is a hypothesis, not a diagnosis.** The `FAILED *.html`
dump from the next production run is what will settle it.

Re-run 2026-08-25 after the v3.2 change: **46 rows, exit 0, all seven lists matching**.
Forced-fallback test: requests 13 panels == browser 13 panels, identical name set,
diacritics intact.

### v3.2 did not fix it — and it ruled out the leading suspect

The 2026-09-02 production run failed the same way, on the same list:

```
File "...\AL-AFSA\AL-AFSA.py", line 319, in _browser_html   raise RuntimeError(
RuntimeError: SKIPPED - Chrome never produced the accordion for
  https://amf.gov.al/ts_shoqeri_sigurimi.asp within 120s after 6 attempt(s)
  (loaded 630998 bytes with no accordion in it;
   landed on https://amf.gov.al/ts_shoqeri_sigurimi.asp)
```

What this establishes:

- **Not a redirect.** The browser landed on the requested URL.
- **Not a challenge still clearing.** Six navigations in 120 s produced the same result, so
  raising `CLEARANCE_TIMEOUT` is pointless.
- **Not a dirty shared Chrome profile.** v3.2 already isolates the browser (`auto_port(True)`,
  `--disable-extensions`) and the byte count barely moved: **632133 (2026-08-26) →
  630998 (2026-09-02)**, Δ 1135 over a week. That was the leading hypothesis and it is now
  effectively dead — *unless* the log carries the `[!] isolated Chrome failed to start`
  line, which has not been checked.
- **It is a stable substitute page**, not corrupted or truncated HTML: ~631 KB reproducibly,
  against 127206 bytes / 13 panels measured from the dev Mac over plain `requests` on
  2026-09-02.

**What that 631 KB page is remains unknown.** Current suspects, in order, all unverified:
a corporate proxy/DLP block page (they embed base64 assets and run to hundreds of KB, and
would also explain the `requests` 403); a Cloudflare challenge whose markers fall outside
the 800-character window `looks_like_challenge()` sniffs; a content-injection agent
rewriting class attributes. **The `FAILED *.html` dump v3.2 writes into the control
server's `tempfolder` is what settles this, and it has not yet been read.**

### What changed in v3.3

Failure containment only — no transport, parsing, mapping or schema change. This does
**not** fix the list-1 failure above; it stops that failure from costing the other six
lists.

- **One list failing no longer ends the run.** Everything raised while fetching *or*
  parsing a list is caught per list; the list is named in the summary and the loop moves
  on. Same convention as `JO CBJ v4` (`!! LIST n SKIPPED` / `!! INCOMPLETE`).
- **A half-parsed list is rolled back to nothing.** If a list dies mid-parse, the rows it
  already wrote are deleted. A partial list is worse than an absent one — the entities it
  never reached would load as if they had been de-listed, and the reconciliation count
  would agree with itself.
- **All lists failing still fails loudly.** If nothing at all was scraped, no workbook is
  written and the script raises. An empty file is not a small load; it is a load that
  de-lists every AFSA entity.
- **The incompleteness is printed twice** — in the reconciliation block and as the last
  line of the run, because a partial file whose log tail looks clean is exactly how a
  partial load gets shipped.

Verified 2026-09-02 on the dev Mac, three runs:

| test | result |
|---|---|
| unmodified | 46 rows, 7/7 lists matching source panel counts, `transport: requests` |
| injected failure on list 1, panel 5 | list 1 → **0** rows (4 already-written rows rolled back), total **33**, `!! INCOMPLETE` shown, saved workbook has no `ListCode == '1'` row |
| injected failure on all 7 lists | `RuntimeError`, **no .xlsx written**, non-zero exit |

**Still not verified on the control server.**

---

## Judgment calls for the requester

1. **List 3 and list 7 ListLabel.** Set to `4`. Ten of eleven list-3 entries and all four
   list-7 entries are banks by corporate form, but AFSA licenses them for investment
   services / depositary activity, not banking. If the convention is "label by the entity's
   corporate nature" rather than "by the register's subject", these become `1`. **Please
   confirm.**
2. **`Fax` is always empty.** The site publishes a single merged `Tel./Faks` field with no
   marker distinguishing the two (e.g. `+355 4 2233 308/ 253 407/408/ +355 4 2250 220`).
   Everything goes to `Phone`; splitting would be guesswork. Confirm this is acceptable.
3. **`City` is derived, not published.** AFSA gives only a free-text `Adresa e Selisë`.
   `pick_city()` matches a list of Albanian administrative centres against the address; all
   31 non-fund rows resolved to `Tiranë`, which is plausible (all these entities are
   Tirana-based) but is *derived*, not sourced. Say the word and it can be blanked instead.
4. **Investment funds are not legal entities.** List 6's 15 rows are funds, and their
   `Name - Mother Company` is the management company (`NËN ADMINISTRIMIN E ...`). If funds
   should instead be dropped, or if the *management company* should be the `Name` with the
   fund as a product, this needs a decision.
5. **The fund depositary is parsed but not stored.** `parse_fund_body()` also extracts
   `DEPOZITAR I FONDIT: <bank>`, but the fixed 43-key schema has no field for it. It is
   currently discarded. If it matters, name a target column.
6. **`ALBSIG sh.a.` has no licence number.** Its licence line carries a date but no `Nr.`,
   so `InternalID_1` is empty while `RegulationDate` is populated. Source limitation.
7. **`ListValidityDate` is left empty** — AFSA publishes no "as of" date on these pages.

---

## Known future breakage risks

- The whole parser hangs off the Bootstrap 3 class names `div.panel.panel-default`,
  `div.row`, `div.col-md-3`, `div.col-md-9`. A front-end refresh to Bootstrap 5 (which
  dropped `.panel-*` entirely in favour of `.accordion-*`) would break all seven lists at
  once. The failure would be loud — `get_soup()` raises rather than returning 0 rows.
- The Cloudflare e-mail-protection scheme could change or be disabled; `decode_cfemail()`
  returns `''` on any malformed payload rather than raising, so e-mails would silently go
  blank. Worth an assertion if e-mail coverage matters.
- `parse_license()` covers the three phrasings currently live. A fourth wording (e.g. a
  licence with no `Nr.` token, as already seen for ALBSIG) yields an empty `InternalID_1`
  without warning.
- `AL_CITIES` is a static gazetteer; an entity outside those towns would get an empty `City`.
- `.asp` endpoints suggest an ageing stack; these are exactly the URLs most likely to be
  re-platformed. The URLs were verified live on 2026-08-20.

## Not verified

- Whether AFSA publishes an English mirror of these seven registers (`ListLanguage` is
  therefore honestly `SQ`, the language actually parsed).
- Whether AFSA declares official register totals anywhere else on the site; no total is
  printed on the seven pages themselves.
- A **successful** run on the Windows control server. Every version so far has been written
  and verified on macOS with the global `python3`; on the control server v3.0 died on a
  Cloudflare `403`, and v3.1/v3.2 died on the ~631 KB no-accordion page described above.
  v3.3 keeps the other six lists alive but has not been run there either.
- What the ~631 KB page served to the control server actually is. The `FAILED *.html` dump
  in that box's `tempfolder` has not been read.
- Whether the control-server log carries the `[!] isolated Chrome failed to start` line. If
  it does, the shared-dirty-profile hypothesis is back in play.
