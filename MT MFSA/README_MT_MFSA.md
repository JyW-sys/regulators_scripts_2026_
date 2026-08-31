# MT MFSA — Malta Financial Services Authority

Jira: **DECD-6834** · RegCtry `MT` · RegCode `MFSA`
Run verified: **2026-08-20**, `MT_MFSA_v3.py` / `MT_MFSA_v3.ipynb` (notebook executed end-to-end, **0 error cells**).

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows (observed) |
|---|---|---|---|---|---|---|
| 1 | `1` | `3` | License Holders | https://www.mfsa.mt/financial-services-register/ → iframe **https://fsr.mfsa.mt** | JSON API (no browser) | **12 583** |

**ListLabel = 3.** The ticket defines a single list, and that one register is the whole MFSA
population: banking *and* insurance *and* investment services, pensions, trustees, crypto, etc.
Under the house rule (1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else) a
combined bank + insurance register is `3`. See "Judgment calls" — if the requester would rather
have one list per Sector, the scraper already carries the Sector in `CoType` and splitting is a
one-line change.

## The site, and how to get data out of it

The ticket URL is **live but is only a wrapper**. `https://www.mfsa.mt/financial-services-register/`
is a WordPress page whose entire content is:

```html
<iframe title="Financial Service Register" src="https://fsr.mfsa.mt" width="100%" height="600">
```

The real application is a separate ASP.NET Core app at `https://fsr.mfsa.mt`. Scraping the
WordPress page yields nothing.

**A clean JSON API exists — no browser, no driver.** The endpoints are named in plain sight in
`https://fsr.mfsa.mt/js/custom/searchlicenceholder.js`:

| Endpoint | Purpose |
|---|---|
| `GET /LicenceTypes/getParentLicenceTypes` | the **Sector** dropdown → 17 sectors |
| `GET /LicenceTypes/getLicenceTypesByParentId?parentLicenceTypeId=<id>` | the **Authorisation** dropdown → 186 types |
| `GET /Licences/getLicenceHoldersByLicenceTypeId?licenceTypeId=<id>` | the result grid (holders + their licences) |
| `GET /Licences/ViewLicence?id=<licenceId>` | per-licence detail page (HTML) — **not used**, see below |

Both dropdowns are discovered at runtime; nothing is hard-coded, so a new sector or authorisation
type is picked up automatically.

### Site quirks that will bite later

1. **Session cookies are mandatory.** The JSON endpoints return **HTTP 400 with a zero-length
   body** unless the client has first `GET`-ed `https://fsr.mfsa.mt/` and holds the `MFSA` and
   `.AspNetCore.Antiforgery.*` cookies. `make_session()` does this. A bare `requests.get` on the
   API 400s — this looks like a dead endpoint but is not.
2. **Aggressive rate limiting (HTTP 429).** Verified the hard way: an 8-thread harvest got **429
   on 113 of 186** authorisation types. The scraper is deliberately **serial with a 0.4 s delay**
   and escalating 5/10/15… second backoff. Do not parallelise this. Full run ≈ 2 minutes.
3. **Cloudflare is in front of `fsr.mfsa.mt`** (a JSD challenge script is injected into the HTML).
   It did **not** challenge plain `requests` during this run, but if it starts to, fall back to
   DrissionPage with `page.listen.start()` — the endpoints above are unchanged.
4. **`ViewLicence` is `GET` with `?id=`**, and the `licenceId` is an ASP.NET Data-Protection blob
   (`CfDJ8…`) that is **regenerated on every grid call** — it cannot be cached or bookmarked
   between runs.
5. **31 of 186 authorisation types legitimately return 0 holders** (the whole `Listing` sector is
   empty). That is the site's own state, not a scrape failure. The run log prints the count so a
   sudden jump is visible.
6. **The site prints no total anywhere** — there is no "N results" label to reconcile against.
   Reconciliation is therefore structural (see below), not against a declared figure.

## Row model and reconciliation

The site renders **one line per licence**, nested under a holder's name: a holder with 4
authorisations occupies 4 lines. The output mirrors that exactly — **one row per
(holder, licence)**. `drop_duplicates()` is never called.

Observed on the 2026-08-20 run:

| Quantity | Value |
|---|---|
| Sectors discovered | 17 |
| Authorisation types discovered | 186 |
| Authorisation types fetched successfully | **186 / 186** (0 failures) |
| Authorisation types returning 0 holders | 31 |
| Holder entries returned by the API | 12 258 |
| **Licence rows written** | **12 583** |

12 583 > 12 258 because some holders carry more than one licence *within the same* authorisation
type. Every one of the 43 columns held 12 583 values (asserted), and the workbook read back as
12 583 rows × 43 columns.

### Per-sector row counts (observed)

| Sector (`CoType`) | Rows |
|---|---|
| Insurance | 5 764 |
| Securities and Markets | 2 157 |
| Markets in Crypto Assets | 1 262 |
| Investment Services | 994 |
| Financial Institutions | 993 |
| Banking | 436 |
| Company Service Providers | 400 |
| Trustees and Other Fiduciaries | 218 |
| Securitisation | 128 |
| Pensions | 124 |
| VFA Framework | 57 |
| Crowdfunding | 33 |
| Credit Agreements for Consumers (Residential Immovable Property) | 8 |
| Financial Markets | 5 |
| Credit Servicers | 3 |
| Benchmarks | 1 |
| Listing | 0 |
| **TOTAL** | **12 583** |

## Field mapping (List 1)

| Column | Source | Note |
|---|---|---|
| `Name` | `licenceHolderName` | whitespace-collapsed |
| `InternalID_1` / `_type` | `companyId` / `"MBR Registration Code"` | Maltese registry code, e.g. `C 2192`, `OC 198` |
| `InternalID_2` / `_type` | `identification` / `"MFSA Authorised Person ID"` | e.g. `APS` |
| `InternalID_3` / `_type` | `licenceTypeId` / `"MFSA Licence Type ID"` | traceability back to the API |
| `CoType` | Sector (parent licence type) | e.g. `Banking`, `Insurance` |
| `License_Type` | Authorisation name, incl. the parent suffix the site renders | via `licence_label()` |
| `RegulationType` | derived from `licenceStatus` | see below |
| `Cntry` | `'MT'` | **see judgment call #2** |
| `RegCtry` / `RegCode` | `'MT'` / `'MFSA'` | hard-coded literals, never derived by splitting a dict key |
| `ListCode` / `ListLabel` / `ListLanguage` / `ListName` | `'1'` / `'3'` / `'EN'` / `'License Holders'` | |
| `ListProcessDate` | `now.strftime('%Y-%m-%d')` | `2026-08-20` on this run |
| everything else | `''` | the grid API carries no address/phone/email/LEI — see judgment call #1 |

### RegulationType — status breakdown (observed, source-declared wording)

`'Licence Authorised'` → **`Regulated`** (6 707 rows). Every other status is written through
**verbatim**, so nothing is lost and the requester can remap without a re-scrape:

| Status | Rows | | Status | Rows |
|---|---|---|---|---|
| Licence Authorised → `Regulated` | 6 707 | | Registration Cancelled Voluntarily | 47 |
| EU/EEA Authorised | 2 220 | | Licence Suspended Voluntarily | 33 |
| Notified | 1 362 | | Authorisation Revoked | 32 |
| Licence Surrendered Voluntarily | 1 117 | | Licence Surrendered Vol. Following Merger | 30 |
| Deregistered | 372 | | Registered | 22 |
| Termination | 345 | | Denotified Voluntarily | 19 |
| EEA Authorised | 97 | | Licence Suspended Regulatory | 15 |
| Licence Cancelled Regulatory | 66 | | Acknowledged | 14 |
| Approved | 53 | | Not Applicable | 12 |
| Licence Run-off | 11 | | Removed from Register Regulatory | 5 |
| Licence Authorised (Cancellation Pending) | 2 | | Pending Strike Off / Exempted | 1 / 1 |

## What was wrong with v1 / v2 / palame

Audited directly (all three left untouched on disk).

| Defect | v1 | v2 | palame |
|---|---|---|---|
| **`sqldict` has 44 keys — an extra `'Check'`** (schema violation; fails QA on schema alone) | yes | yes | yes |
| `RegCode` value | `'MFSA'` — **correct** | `'MFSA'` — **correct** | derived via `reg.split(' ')` for `ListCode` — the fragile copy-paste pattern that produced a wrong regulator code elsewhere in this repo |
| **`ListLabel` populated with `licences[0]['licenceTypeName']`** — a licence-type *string* where the schema wants `1`/`2`/`3`/`4` | yes | yes | — |
| Selenium / ChromeDriver (no browser on the control server) | — | yes | yes |
| `drop_duplicates()` before save (forbidden — corrupts row count) | — | — | yes |
| `writer.save()` — removed from modern pandas/XlsxWriter, raises `AttributeError` | yes | yes | — |
| Output written to `tempfolder/` instead of the regulator folder | yes | yes | yes |

`RegCode` was **correct** in v1 and v2 — the CN NFRA-style wrong-regulator bug is **not** present
here. No notebook populated `Name - Mother Company` with the entity's own name (v3 leaves it
blank: 0 non-blank values, asserted).

### What v3 changes

- Exactly **43 keys**, asserted at build time and again as column order immediately before
  `to_excel`, and re-asserted after reading the workbook back.
- Single `add_row(**kw)` that appends to every key and raises `KeyError` on an unknown column.
- Pure `requests` — no Selenium, no ChromeDriver, no `win32com`, no Windows paths.
- Serial + backoff to survive the 429 limiter; retries with escalating cooldown.
- Sectors and authorisation types **discovered every run**; no hard-coded enumeration.
- Output lands in the regulator folder, not `tempfolder/`.
- Loud reconciliation block + status histogram in the run log.
- ID/Zip/Phone columns pinned to Excel text format, then **read back and asserted**
  (`InternalID_1` sample round-tripped as `'OC 198'`, not a float).

## Judgment calls for the requester

1. **Address / phone / website / LEI are NOT in the output.** The grid API returns only name,
   MBR code, person ID, authorisation and status. The richer fields exist, but one HTTP request
   *per licence* deep — `GET /Licences/ViewLicence?id=…` returns a page carrying **MBR
   Registration Code, Authorised Person ID, Company Registration Date, LEI Code, Registered
   Address, Business Address, Website, Authorisation Issue Date**. I verified this on one record
   (APS BANK P.L.C.: LEI `213800A1O379I6DMCU10`, registered address, `www.apsbank.com.mt`).
   Enriching all 12 583 rows means 12 583 extra requests against a 429-limiting server — roughly
   1.5–2 hours serially. **Decision needed: is the enrichment wanted?** If yes this should be a
   second pass with a resumable cache; the detail parser is *not* written yet.
2. **`Cntry` is hard-coded `'MT'`, and that is wrong for at least 2 317 rows.** The register
   includes EEA passporting firms — `EU/EEA Authorised` (2 220) + `EEA Authorised` (97), plus
   whole authorisation types named "Freedom of Services and Establishments …". These are foreign
   entities. **The grid API exposes no country field**, so per-row country is only obtainable via
   the detail page in #1. Flagging rather than guessing.
3. **`RegulationType` for the positive-but-not-"Licence Authorised" statuses.** `EU/EEA
   Authorised` (2 220), `Notified` (1 362), `Registered` (22), `Approved` (53), `Acknowledged`
   (14) and `Exempted` (1) are *active* entries, not withdrawals — arguably all `Regulated`.
   The file currently carries the verbatim MFSA wording for these. Confirm the intended mapping;
   no re-scrape is needed to apply it.
4. **One list or seventeen?** The ticket says one list ("select in the Sector tab … and the same
   in the Authorisation tab"). Delivered as one list of 12 583 rows with the sector in `CoType`.
   Splitting per sector would let `ListLabel` be exact per sector (Banking → 1, Insurance → 2,
   Investment/Pensions/Trustees → 4) instead of the combined `3`.
5. **Multi-licence holders produce multiple rows** (12 583 rows from 12 258 holder entries), which
   matches what the site renders. Confirm that is the wanted grain.

## Not verified

- **Detail-page (`ViewLicence`) parsing at scale.** Verified the endpoint returns HTTP 200 with
  the field set listed above for **one** licence. No parser was written or tested.
- **Whether the site's own totals agree** — the register prints no result count anywhere, so
  there is no declared figure to reconcile against. Reconciliation here is structural only.
- **Behaviour under Cloudflare challenge.** Cloudflare did not challenge this run; the
  DrissionPage fallback described above is untested for this site.
- **Long-term stability of the 0.4 s delay.** It sufficed on 2026-08-20 (186/186 fetched, zero
  429s); the limiter's exact threshold was not measured.

## Run

```bash
python3 "MT_MFSA_v3.py"        # ~2 minutes, writes MT MFSA SQL Ready <timestamp>.xlsx
```
