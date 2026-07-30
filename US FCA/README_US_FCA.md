# US FCA — Farm Credit Administration

Jira: **DECD-6470** (parent epic DECD-3438 — Regulators 2026 — Crawlers)

Latest scraper: **`US_FCA_v4.ipynb`** (+ `US_FCA_v4.py`, the same code for the control server —
regenerate the `.py` from the notebook, never edit both by hand).

## Lists

| ListCode | ListName | Source | ListLabel |
|---|---|---|---|
| 1 | List of "Farm Credit System Institutions" | `https://apps.fca.gov/FCSPublicDirectory/PubSearchInstitution.aspx` | 1 |

`ListLabel = 1` — the Farm Credit System is a network of lending banks, agricultural credit
associations and their service corporations.

## Transport: DrissionPage / Chrome (v4)

v3 used `requests` with a raw-socket preflight. On the control server it aborted at:

```
socket.create_connection(('apps.fca.gov', 443), timeout=15)  ->  socket.timeout
```

**A raw-socket timeout does not prove Chrome is blocked too.** `socket.create_connection` always
goes direct; Chrome follows the Windows system proxy / PAC script, and on a corporate control box
that is often the only route off the network. This is the same asymmetry already recorded for that
machine elsewhere in the project (plain `requests` 403s where DrissionPage gets through).

So v4 drives Chrome via DrissionPage, and `preflight()` probes **both** paths and prints each
result, so the log alone distinguishes the two cases:

| direct TCP | via Chrome | meaning |
|---|---|---|
| blocked | **OK** | proxy-only network — v4 fixes it, the run proceeds |
| blocked | blocked | genuinely no route to `4.79.206.0/24` — needs a US VPN, no code fix exists |
| open | OK | unrestricted network (a US machine) |

### Environment escape hatches

Set on the control server, no code edit required:

| Variable | Effect |
|---|---|
| `US_FCA_PROXY=http://host:port` | passes `--proxy-server` to Chrome. **Try this first** if a normal Chrome window on that machine can open the directory but the script cannot — `auto_port()` starts a clean automation profile that does not inherit a per-profile or extension-based proxy. |
| `US_FCA_HEADLESS=1` | headless, for an unattended session with no interactive desktop. **Leave this off unless you have to.** In testing, the corporate egress proxy rejected *every* headless request — any host, with an F5 `Request Rejected` page rather than a timeout — because the UA string contains `HeadlessChrome`. Headed is the default for that reason. |

### What "success" means to `load_html`

Not "the document is non-empty". Chrome answers an unreachable host — and a WAF answers a
rejected one — with a perfectly valid non-empty HTML page. Accepting that would parse into a row
of blank fields and look like a clean scrape. `load_html` therefore requires the **expected
selector to be present** (`#ctl00_cphMainContent_gvInstitutions` for the grid,
`span[id$="lblUninum"]` for a detail page) and retries otherwise.

A detail page that still fails after 3 attempts **aborts the run**. A short file is worse than no
file — the same reasoning as the 0-row guard in the writer cell.

### Transport verification (on a non-US machine, 2026-07-30)

The network path to FCA could not be tested from here, but the DrissionPage layer itself was:

| Check | Result |
|---|---|
| Chrome launch, `auto_port()`, `set.timeouts()`, `quit()` | OK on DrissionPage 4.1.1.4 |
| reachable page + matching selector | returns HTML, ~1 s |
| valid document, selector absent | returns `''` after retries — correctly refuses |
| unreachable host | returns `''` after ~86 s per attempt — **no indefinite block** |

So a fully blocked `preflight()` takes roughly 4 minutes (3 attempts) before printing the
`[BLOCKED]` diagnosis. That is expected, not a hang.

The parse layer is unchanged from v3 and was re-run against the Wayback fixtures below.

`driver.set.timeouts(page_load=60)` is mandatory, not a nicety: a silently dropped handshake never
fires a load event, so an un-timed `page.get()` blocks in a socket read instead of surfacing an
error the retry loop can act on.

## ⚠️ The origin is geo-restricted to the United States

Every FCA origin host refuses direct connections from the office network. Measured with
`dig` + `nc -z`:

| Host | IP | TCP 443 |
|---|---|---|
| `apps.fca.gov` | 4.79.206.81 | **blocked** |
| `reports.fca.gov` | 4.79.206.80 | **blocked** |
| `ww3.fca.gov` | 4.79.206.88 | **blocked** |
| `ww4.fca.gov` | 4.79.206.89 | **blocked** |
| `www.fca.gov` | Cloudflare CDN | open |

The handshake is **dropped, not reset** — connections hang to timeout, which is the signature of a
geo/IP filter rather than a firewall rejection or an application-level block.

**The Jira note "has CloudFlare" has it backwards.** Cloudflare is not the blocker — it is the only
reason `www.fca.gov` is reachable at all, because that one hostname is served from Cloudflare's edge
rather than from FCA's own `4.79.206.0/24` network. Everything that matters (the directory, the
search page, the detail pages, `reports.fca.gov/CRS/*`) sits on the origin.

`www.fca.gov` was searched for an alternate route to the same data. Every institution path it
advertises — `PubSearchInstitution.aspx`, `PubViewInstitutionsBySysDist.aspx`, `Locator/`,
`reports.fca.gov/CRS/*` — resolves to a blocked host. There is no CDN-served mirror.

No user-agent, header, proxy or retry strategy fixes a dropped TCP handshake. **Run this on a US
VPN or on the Windows control machine.**

`preflight()` opens a TCP socket to `apps.fca.gov:443` before anything else and raises with the
explanation above if it fails. This is deliberate: without it the scraper would have parsed nothing
and written a clean-looking 0-row workbook.

## How the selectors were validated without access

The parser is not guesswork. Both page shapes were recovered from the Wayback Machine (located via
the CDX API, fetched with the `id_` raw-content suffix so no archive chrome is injected) and the
parse functions were run against them:

| Fixture | Result |
|---|---|
| search page (snapshot 2025-10-25) | `#ctl00_cphMainContent_gvInstitutions` found, header `Uninum / Institution Name / District / HQ State / CEO / RSSD`, **65 data rows**, 0 blank names, 0 blank uninums, **no pager links**, districts `AgFirst / AgriBank / CoBank / Service Corporations / Texas` |
| detail page (snapshot 2025-03-05, `?u=2000012`) | 11 of 13 field spans populated; address split `30 E. 7th Street, Suite 700` / `St. Paul` / `MN` / `55101-1810`; charter date `2/1/2020` → `2020-02-01` |

Re-run against these fixtures after the v4 rewrite — the parse layer is byte-identical to v3, only
the transport changed, and it still produces the same fields.

Two things the newer fixtures corrected in this README:

- **The row count is not fixed at 64.** The October 2025 snapshot has 65. Do not treat any
  particular number as the expected output; the pager guard, not a row count, is what protects
  against truncation.
- **The two empty fields are real, not a parse gap.** `?u=2000012` is SunStream Business Services,
  a *Service Corporation*: `lblRSSD` is present but empty and `lblCharterNumber` is absent from the
  page entirely, because service corporations have neither. The grid's RSSD cell is empty for that
  row too, so the `detail.get('rssd') or inst['rssd']` fallback correctly yields `''`. Expect
  `InternalID_2` / `InternalID_3` to be blank for the Service Corporations district.

What remains unverified is only what live access could tell us: today's row count, and whether any
entity type exposes a field shape the two fixtures didn't show.

## Structure

- **Grid** — one page, 64 institutions, no pagination. Detail links are `PubViewInst.aspx?u=NNNNNN`.
  A guard raises if pager links ever appear, rather than silently truncating.
- **Detail** — five tables (`FCS Institution Directory`, `Addresses`, `Charter Information`,
  `Map and Territory Description`, `Comment:`). Every value sits in a `<span>` with a stable id
  suffix: `lblUninum`, `lblShortName`, `lblStatusAndDesc`, `lblPhone`, `lblRSSD`, `lblCEO`,
  `lblChairman`, `lblCharterAddress`, `lblCharterCounty`, `hlWebURL`, `lblInstName`,
  `lblCharterDate`, `lblCharterNumber`.

Both the grid and the detail page are read **by label, never by position** — the grid by header
text, the detail by span id.

## Mapping

| Column | Source |
|---|---|
| `Name` | grid Institution Name |
| `EntryType` | `lblShortName` (abbreviated name) |
| `Typology` | grid District (AgFirst, AgriBank, CoBank, Texas, Service Corporations) |
| `License_Type` | `lblStatusAndDesc` |
| `InternalID_1` / `_type` | `lblUninum` / `FCA Institution Number` |
| `InternalID_2` / `_type` | `lblRSSD` / `RSSD Number` |
| `InternalID_3` / `_type` | `lblCharterNumber` / `Charter Number` |
| `Address_1` / `City` / `Zip` | `lblCharterAddress`, split on `City, ST ZIP` |
| `Address_2` | US state |
| `Cntry` | `US` |
| `Name - Mother Company` | `lblInstName` (official charter name) |
| `RegulationDate` | `lblCharterDate`, `m/d/Y` → `%Y-%m-%d` |
| `RegulationType` | `Regulated` |

## Fixed from v1

1. **`Cntry` held the US state.** v1 did `sqldict['Cntry'].append(state_)`, so every row read
   `TX`, `MN`, `SC` … instead of `US`. v3 sets `Cntry = 'US'` and moves the state to `Address_2`.
2. **Positional detail parsing.** v1 indexed `maintable[0]` … `maintable[6]`. The main table's rows
   carry 3 cells for the first five fields and 2 for the last two, so any inserted or reordered row
   shifts every field by one — silently. v3 matches on span id.
3. **Hardcoded Windows `scriptfolder`** (`C:\Users\wuj1\OneDrive - Moody's\…`) → the
   `try: __file__ / except NameError: os.getcwd()` idiom from `CLAUDE.md`.
4. **Non-schema `'Check'` key** in `sqldict`, violating the frozen 43-column schema. Removed.
5. **`writer = ExcelWriter(filename)`** was created and never used, leaving an empty file behind.
   Replaced with `df.to_excel(..., sheet_name='SQL Ready', index=False)`.
6. **`ListLabel`, `ListLanguage` never populated.** Now `1` and `EN`.
7. **No empty-output guard.** v3 raises rather than writing a 0-row workbook — the failure mode that
   let ES BES v1.2 ship nothing while looking successful. Verified: the aborted run on this machine
   writes no file.

## Fixed from v3 (v4)

1. **`requests` → DrissionPage/Chrome**, and the raw-socket preflight → a dual probe that reports
   the direct path and the Chrome path separately. See *Transport* above for why a socket timeout
   was never sufficient evidence that the scraper could not run.
2. **A non-empty document is no longer treated as a successful load.** The selector must be
   present. Without this, Chrome's own error page and any WAF interstitial would parse into rows
   of blank fields — the exact class of silent failure this README already guards against
   elsewhere. Observed live during v4 testing, which is what prompted the check.
3. **`driver.quit()` in a `finally`**, so an aborted run does not leave an orphaned Chrome process
   on the control server.
4. **A `.py` twin** (`US_FCA_v4.py`) is now kept in the folder, generated from the notebook by
   splitting on the `#--- Begin_* ---` banners, so the control server no longer runs a
   hand-maintained copy that can drift from the notebook.

## Not carried over

- **County** (`lblCharterCounty`) is published but has no home in the frozen 43-column schema, so it
  is deliberately dropped rather than overloaded into an unrelated column. Same treatment as GB
  IMFSC's trading names.
- **CEO / Chairman** are captured by the grid and detail parse but not emitted — the schema has no
  officer column.

## What v2 was

`US_FCA_v2.ipynb` is **not a scraper**. It is a six-cell cookie-debugging scratchpad that prints
cookies, injects stale 2026 GA cookies and checks for `cf_clearance`. It never parses the grid,
never builds `sqldict` and never writes output. It was presumably an attempt to defeat what was
assumed to be a Cloudflare block — which, per the finding above, was never the problem. Superseded.

## Last run

**Never completed. No output file exists yet.** That is the honest status of this ticket, not a
soft "needs a retry".

| Date | Where | Outcome |
|---|---|---|
| 2026-07-29 | office Mac | v3 aborted at `preflight()` — `socket.timeout` on `apps.fca.gov:443`. No file. |
| 2026-07-29 | control server | v3 aborted the same way. No file. |
| 2026-07-30 | office Mac | v4 written; transport layer and parse layer verified, network path still unreachable from here. No file. |

### Next step — run v4 on the control server and read the two preflight lines

```
[INFO] : - direct TCP apps.fca.gov:443 : ...
[INFO] : - Chrome page load           : ...
```

- **`BLOCKED` then `OK`** → v4 solved it, the run continues on its own. Nothing further to do.
- **`BLOCKED` then `BLOCKED`** → open the directory URL in a normal Chrome window on that machine.
  - If **it loads**, the automation profile is missing the proxy: set `US_FCA_PROXY` (see above)
    and re-run. Chrome's own proxy is at `chrome://net-internals/#proxy`.
  - If **it does not load either**, the machine genuinely has no route to `4.79.206.0/24` and no
    code change can help. It needs a US VPN, and that should go back to the ticket owner as an
    infrastructure request rather than another scraper revision.

Expect roughly 4 minutes before the `[BLOCKED]` message appears — 3 attempts × a 60 s page-load
timeout. That is the diagnosis running, not a hang.
