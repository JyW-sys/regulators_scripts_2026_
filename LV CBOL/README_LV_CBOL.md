# LV CBOL — Latvijas Banka (Bank of Latvia)

**Jira:** DECD-6826
**Register:** Financial Market Participant Register
**Entry point:** https://www.bank.lv/en/financial-market-participant-register
**Version:** v3 (full rebuild — v1 and v2 are dead, see "What changed")
**Last run:** 2026-08-20 → `LV CBOL SQL Ready 2026-08-20 18.45.00.xlsx`, **460 rows**

---

## Lists

Row counts below are **observed** from the 2026-08-20 run. Every list reconciled exactly
against the count the register prints itself ("Found N results") — zero mismatches.

| ListNr | ListCode | ListLabel | ListName | Segment (discovered alias) | Source | Rows |
|---|---|---|---|---|---|---|
| 1 | LV CBOL 1 | 4 | Investment service providers | `3-alternative-investment-fund-managers` | JSON | 33 |
| 2 | LV CBOL 2 | 2 | Insurance companies | `51-insurance-companies` | JSON | 7 |
| 3 | LV CBOL 3 | 2 | Insurance Intermediaries | `137-insurance-intermediaries` | JSON | 90 |
| 4 | LV CBOL 4 | 4 | Financial instruments market | `107-financial-instruments-market` | JSON | 111 |
| 5 | LV CBOL 5 | 4 | Financial holdings | `471-financial-holdings` | JSON | 3 |
| 6 | LV CBOL 6 | 4 | Investment service providers | `111-investment-service-providers` | JSON | 28 |
| 7 | LV CBOL 7 | 4 | Investment management companies | `1-investment-management-companies` | JSON | 76 |
| 8 | LV CBOL 8 | 4 | Crowdfunding service providers | `466-crowdfunding-service-providers` | JSON | 8 |
| 9 | LV CBOL 9 | 1 | Co-operative Credit Unions | `94-co-operative-credit-unions` | JSON | 20 |
| 10 | LV CBOL 10 | 1 | Credit institutions | `41-credit-institutions` | JSON | 11 |
| 11 | LV CBOL 11 | 1 | Payment service providers | `236-payment-service-providers` | JSON | 44 |
| 12 | LV CBOL 12 | 4 | Pension Funds | `135-pension-funds` | JSON | 14 |
| 13 | LV CBOL 13 | 4 | Foreign exchange trading companies | `469-foreign-exchange-trading-companies` | JSON | 15 |
| | | | | | **TOTAL** | **460** |

Lists 1 and 6 intentionally share the ListName "Investment service providers" and list 7
merges what used to be two URLs — kept as separate ListNr/ListCode entries exactly as the
ticket numbers them.

### ListLabel reasoning
House rule: `1` = bank, `2` = insurance, `3` = both, `4` = everything else.
- **2 (insurance)** — lists 2 and 3 are insurers and insurance intermediaries.
- **1 (bank)** — list 9 (credit unions), list 10 (credit institutions/banks) and list 11
  (payment service providers, whose selection includes `Banks` and credit institutions).
- **4 (other)** — funds, holdings, instruments market, pension funds, FX and crowdfunding.

List 11 is the softest call: it is a payment-services register that happens to contain
banks. Flagged for the requester to overturn if they would rather see `4`.

### RegulationType
All 460 rows are `Regulated`. Every list is a positive/authorised register, and all
not-in-good-standing sub-segments were kept out (below).

---

## Row-count reconciliation

The register prints its own total for any filter, so the scraper parses it and compares.
The run log prints `reconciled: site declares N / parsed N` per list and a loud
`*** MISMATCH ***` otherwise. **All 13 lists reconciled on the last run.**

Note the gap between a segment's *whole* size and the rows taken — this is the ticket's
sub-segment selection working, not data loss. Example: credit institutions has 424
entities in total, but the ticket asks only for Banks + Representative offices = 11.
The other 413 are EEA passporting entities (`Freedom to provide services` = 403,
`Freedom of establishment` = 5) plus 5 in liquidation.

| List | Whole segment | Taken | Why the difference |
|---|---|---|---|
| 1 | 202 | 33 | only Licensed + Registered managers |
| 2 | 496 | 7 | only Life + Non-life; the other 489 are EEA branches/FPS/liquidation |
| 3 | 1524 | 90 | all categories except the two EEA ones |
| 4 | 203 | 111 | Depositary + Issuers + Regulated market organizers |
| 6 | 300 | 28 | Investment firms + Credit institutions + Investment management companies |
| 10 | 424 | 11 | Banks (10) + Representative offices (1) |
| 11 | 1107 | 44 | the six sub-segments named in the ticket comment |

Sub-segments partition their parent exactly — verified on credit institutions:
10 + 5 + 403 + 1 + 5 = 424. No double counting, and no row is deduped.

---

## Site quirks (things that will break this later)

1. **The old site is gone.** Every `uzraudziba.bank.lv/en/market/*` URL in the ticket
   301-redirects to one landing page on `www.bank.lv`. Two different old URLs return
   byte-identical HTML. The ticket's URL column is therefore stale — the URLs above are
   the live equivalents.
2. **The listing is JS-paginated with `<button value="N">`, not links.** There are no
   pagination hrefs to follow. `?page=N` works, but `start=` / `offset=` / `p=` /
   `limitstart=` are **silently ignored and return page 1 with HTTP 200** — a soft-404
   trap that would produce 10 rows repeated forever.
3. **`?format=json` is the stable way in.** It returns `resultCount`, `results`,
   `childSegments` and `tags`. `results`/`childSegments` are HTML *fragments*, not
   structured data, so they still need BeautifulSoup. `&limit=5000` returns the whole
   result set in one request and removes pagination entirely. `limit=0` is **not**
   "unlimited" — it drops the `results` key and will `KeyError`.
4. **Sub-segments reuse the same `segments=` parameter** as top-level segments, and
   accept a comma-separated list. `segments=42-banks,50-representative-offices-...`
   returns 11.
5. **Duplicate sub-segment titles under one parent.** Financial instruments market has
   *two* `Freedom of establishement` entries (`478-` and `480-`) and two
   `Freedom to provide services` (`479-`, `481-`). Match on alias, never assume titles
   are unique. Note the site's own spelling "establishement" is inconsistent with
   "establishment" elsewhere — matching is accent-stripped substring, never `==`.
6. **Latvian diacritics.** Names carry ā č ē ģ ī ķ ļ ņ š ū ž. All title matching goes
   through NFKD accent-strip + NFKC + lowercase.
7. **Excel eats registration numbers.** `40003764029` becomes `4.000376e+10` unless the
   ID columns are pinned to text before `to_excel`. Handled; do not remove that block.
8. **Segment IDs are numeric and unstable across renames** (`1000-latvian-investment-
   management-companies` sits next to `1-investment-management-companies`). Nothing is
   hard-coded — segments come from the landing page and sub-segments from
   `input[data-alias]` each run, and any keyword matching nothing prints
   `SKIPPED — no sub-segment whose title contains '<keyword>'`.

No Cloudflare, no JS rendering needed, no Selenium. Plain `requests` + BeautifulSoup with
`verify=False` for the corporate TLS proxy.

---

## Field mapping

Populated from the listing rows (same for all 13 lists):

| Column | Source |
|---|---|
| `Name` | `h2` inside `.result-content` |
| `InternalID_1` | `Reg. Nr. <n>` info-item (text-pinned) |
| `InternalID_1_type` | `'Registration number'` when a number is present |
| `Cntry` | final info-item (country of origin) |
| `CoType` | the entity's other segment tags, `; ` joined |
| `Typology` / `ListName` | per ticket ListName |
| `RegulationType` | `'Regulated'` |
| `RegCtry` | `'Latvia'` |
| `ListCode` | `LV CBOL <nr>` |
| `ListLanguage` | `'EN'` |
| `ListProcessDate` | `now.strftime('%Y-%m-%d')` |

**Empty by design:** `Address_1`, `City`, `Zip`, and licence dates. See below.
75 of 460 rows have an empty `InternalID_1` — these are foreign entities the register
lists without a Latvian registration number. Not a parsing failure.

---

## What changed vs v1/v2, and why

v2 could not produce a single row, and would not have run in production even if the site
were unchanged:

| Defect in v1/v2 | v3 |
|---|---|
| Scrapes `uzraudziba.bank.lv/en/market/*` — every URL now 301s to one page | targets `www.bank.lv` register |
| Selectors `div.categories-list`, `div.posts-block` — **0 occurrences** on the live site | `.result-content` from the JSON fragment |
| **Selenium + ChromeDriver** — banned on the control server (no Windows automation) | plain `requests` |
| Hard-coded `C:\Users\wuj1\OneDrive - Moody's\...` | `os.path.dirname(os.path.abspath(__file__))` with notebook fallback |
| **`sqldict` had a 44th key `'Check'`** — schema violation | exactly the fixed 43 keys, asserted before write |
| Rows built as loose dicts, columns could drift | single `add_row(**kw)` writing all 43 keys, raising on unknown |
| Hard-coded `skip_by_reg` URL-substring lists per regulator | sub-segments discovered each run, selected by title keyword |
| 12 of 13 lists commented out — only list 11 live | all 13 lists run |
| Crawled category trees with `?l=1..200` probing | one JSON call per list |

---

## Judgment calls for the requester

1. **List 8 (Crowdfunding) — the ticket comment cannot be satisfied as written.**
   It says "Extract the entities under *Service providers from the EEA*", but the
   crowdfunding segment has **no sub-segments at all** on the new site. v3 takes the whole
   segment (8 entities). Confirm that is what is wanted.
2. **List 11 sub-segment "Co-operative credit unions" does not exist** under Payment
   service providers on the new site. The ticket names it; the register does not have it
   there (it is its own top-level segment, already covered as list 9). The other six named
   sub-segments were all found and used. Confirm no double count is wanted.
3. **Not-in-good-standing sub-segments are excluded**, per v2's precedent and because the
   ticket does not ask for them. The scraper carries an `EXCLUDE_ALWAYS` guard for
   `liquidation` / `insolvent` / `suspended`. In practice the ticket's own include-rules
   never selected them, so **nothing was actively dropped by that guard on this run** — but
   the requester should know these exist and can be added as a cancelled/revoked list:
   - `169-credit-institutions-in-liquidation` (5)
   - `151-insurance-companies-in-liquidation`, `152-insolvent-insurance-companies`
   - `159-provision-of-services-suspended`, `155-provision-of-payment-services-suspended`
4. **`Address_1` / `City` / `Zip` and licence dates are empty.** Detail pages carry legal
   address and per-licence valid-from dates, but they are **~1.1 MB each**; 460 entities
   is roughly **500 MB** of transfer and a much longer run. `parse_detail()` is implemented
   and working behind `FETCH_DETAIL = False` — flip one flag to enable, no rewrite needed.
   Requester decides whether the address is worth the cost.
5. **`ListLabel` for list 11** — see reasoning above; `1` vs `4` is arguable.
6. **The register also exposes a `202-crypto-asset-market` segment (14 entities)** that
   the ticket does not mention. Not scraped. Likely worth a follow-up ticket.

---

## Running

```bash
python3 LV_CBOL_v3.py
```

Writes `LV CBOL SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx` (sheet `SQL Ready`) into this
folder — not `tempfolder/`. The notebook `LV_CBOL_v3.ipynb` is generated from the `.py`
via the `#---- Begin_<name> ----` markers and executes the identical code.
