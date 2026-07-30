# GB IMFSC — Isle of Man Financial Services Authority

Jira: **DECD-6468** (parent epic DECD-3438 — Regulators 2026 — Crawlers)

Latest scraper: **`GB_IMFSC_v1.ipynb`** — new build, no prior version.

## Lists

| ListCode | ListName | Source | ListLabel |
|---|---|---|---|
| 1 | All entities currently regulated by the Isle of Man Financial Services Authority | `https://www.iomfsa.im/register-results?entity-name=&entity-current=on&BusinessType=1…20` | 3 |

The Jira comment says *"click all checkboxes and uncheck Former entity"*. That state is fully
expressible in the query string, so the scraper hits the pre-filtered URL directly rather than
driving checkboxes — `entity-current=on` is the "not former" filter and `BusinessType=1…20` is
all twenty categories.

## How it works

`requests` + BeautifulSoup — the register is entirely server-rendered, no JS, no cookies, no
auth. `verify=False` is set on the session, required behind the corporate TLS proxy.

Three stages:

1. **Paginate** `&Page=N` over the filtered results, keeping **every** result row.
   Stops on wrap detection (the site serves page 1 again rather than 404-ing past the end).
2. **Detail fetch**, one request per *unique* detail href, cached — the fields the results grid
   does not carry (address, reference number, dates, licence classes).
3. **Emit** one row per result-grid row, joining the cached detail record back on the href.

## Row grain — one row per grid row, not per entity

**The output row count equals the site's visible result count.** 39 pages × 20 = **780 rows**,
over **666 unique detail pages**.

95 entities — all in the `licence-holders` register — are published under more than one business
type. They share one detail page and one Reference Number, but hold a **separate licence class per
business type**, each with its own Date Issued. Acclaim Limited (ref 1020) is typical:

| Grid row (Business Type) | Licence class on the detail page | Date Issued |
|---|---|---|
| Services to Collective Investment Schemes | Class 3 | 19/02/2016 |
| Corporate Services | Class 4 | 01/01/2009 |
| Trust Services | Class 5 | 30/05/2012 |

v1 de-duplicated on the detail href, which collapsed 780 → 666 and discarded two of those three
dates (`RegulationDate` fell back to `min()`). Stage 3 now matches the grid row's business type to
its licence class by name (`Class 4 - Corporate Services` → `Corporate Services`) and takes that
class's own text into `License_Type` and its own Date Issued into `RegulationDate`.

Consequences to expect in QA:

- `Typology` carries **one** business type per row (v1 joined them with ` | `).
- `InternalID_1` (Reference Number) legitimately repeats across the rows of a multi-class entity —
  it identifies the entity, not the row. `(Name, Typology)` is unique across all 780 rows.
- The 521 rows outside the licence-holders register are one-row-per-entity either way and are
  unaffected.

Detail pages are read **by `<th>` label, never by position** — the field set differs per register
family (a bank, a fund and a TCSP have different row layouts). Labels currently matched:

| Target column | Labels accepted |
|---|---|
| `Address_1` | Registered Office, Principal Trading Address, Address, Place of Business |
| `InternalID_1` | Reference Number, Licence Number, FSA Ref. |
| `RegulationDate` | Date Registered, Date of Registration |
| `CancellationDate` | Date Authorisation/Registration Ceased |
| `License_Type` | Designated Business Category(ies), Scheme Type, Classes/Categories Of Regulated Activity, Class(es) of Regulated Activity |

### `City` / `Cntry` parsing

Manx addresses are frequently single-line and unpunctuated, so a naive comma split picked up
street names as cities (23 street-like values, 130 spurious distinct cities on the first pass).
`City` is now resolved by matching against an explicit list of Isle of Man localities, **last
occurrence wins** (so "Douglas Street, Peel" resolves to Peel), with a comma fallback that
filters out street words (`road`, `street`, `house`, `court`, `quay`, `po box`, …).
Result: 66 distinct cities, none street-like.

`Cntry` is not hardcoded — an IOM postcode or the literal "Isle of Man" gives `IM`, otherwise a
lookup resolves the off-island registrations. Last run: `IM` 759, `GB` 12, `JE` 5, `GG` 3, `IE` 1.

## Decisions worth flagging

- **`ListLabel = 3`, not 4.** This is a single combined register and is *majority* neither bank
  nor insurance (Designated Business 311, corporate/trust services, collective investment
  schemes). But it does carry 13 deposit-taker rows (Deposit Taking 10, Restricted Deposit
  Taking 1, Bank Representative Office 1, Credit Unions 1) and 125 insurance rows (Authorised
  Insurer 99, Insurance Manager 13, Insurance Permit Holder 11, Insurance Groups 2). Labelling
  it 4 would drop all of those from both the bank and the insurance feed, so 3 is the safer
  call. **Confirm with the ticket owner** if the convention here is meant to be strict.
- **Repeated names are intentional, and there are two distinct causes.** Neither is a pagination
  artefact — see *Row grain* above.
  1. *Same name, different detail page and reference number* — 17 firms genuinely hold two
     separate registrations, typically an Investment Business licence *and* a General Insurance
     Business Intermediary registration.
  2. *Same name, same detail page, different licence class* — the 95 multi-class licence holders.
     Each row is a distinct regulated activity with its own class and issue date.
- **Trading names are dropped.** The register publishes "Business Trading Name(s)" per entity.
  The fixed `sqldict` schema has no trading-name column and none of the typed columns fit it, so
  it is deliberately not emitted rather than overloaded into `EntryType` / `CoType`.

## Known field coverage

`Phone` and `Website` are only 2 % filled — the register simply does not publish them for most
entities. `InternalID_1` is 54 %: collective investment schemes carry no reference number.
These are source limitations, not parse gaps.

## Last run

2026-07-30 — **780 rows**, 43 columns, single ListCode 1. Matches the site's visible count.
39 result pages → 780 grid rows over 666 unique detail pages → 666 detail fetches.
All 259 licence-holder rows matched their own licence class (no fallback). No encoding flags.

Coverage vs the 2026-07-29 run (666 rows): `License_Type` 74.6 → 78.3 %, `InternalID_1`
46.4 → 54.1 %, `RegulationDate` 77.0 → 80.4 %. The gains are a mix effect — the licence-holder
register is better populated than the rest and now carries its true weight — plus 44 entities
that previously collapsed to a single `min()` date and now carry a distinct date per class.

### Row-count history

| Date | Rows | Note |
|---|---|---|
| 2026-07-29 | 666 | de-duplicated on detail href — **under-counted by 114**, see *Row grain* |
| 2026-07-30 | 780 | one row per result-grid row, matches the site |
