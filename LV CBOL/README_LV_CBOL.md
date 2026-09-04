# LV CBOL — Latvijas Banka (Bank of Latvia)

**Jira:** DECD-6826
**Register:** Financial Market Participant Register
**Entry point:** https://www.bank.lv/en/financial-market-participant-register
**Version:** v4 (rewritten after the 2026-08-31 ticket update — v1/v2 are dead, v3 is superseded)
**Last run:** 2026-09-02 → `LV CBOL SQL Ready 2026-09-02 17.10.47.xlsx`, **4398 rows**, 13/13 lists reconciled

---

## Why v4 exists

On 2026-08-31 the requester (Guilherme Strelow Hilger) rewrote the ticket description and
commented *"Done, please use the links in the Jira description!"*. Two things changed:

1. **Every list now says "Extract all entities from the link or select the listName in the
   Segment field and extract all entities."** The old description asked for specific
   sub-segments per list; the new one does not. All sub-segment include/exclude selection
   is therefore gone — each list is its parent segment taken whole.
2. **ListNr 1 is renamed.** It was ListName "Investment service providers" pointing at the
   alternative-investment-fund-managers segment (which never matched); it is now
   **"Alternative investment fund managers"**, matching its own URL. ListNr 6 keeps
   "Investment service providers".

Output goes from **460 → 4398 rows**. The old run was not undercounting by accident — it
was correctly implementing an instruction that has since been withdrawn.

---

## Lists

Row counts are **observed** from the 2026-09-02 run. Each list is queried whole, and each
reconciled exactly against the count the register prints itself ("Found N results").

| ListCode | ListLabel | ListName | Segment alias (from the ticket URL) | Rows |
|---|---|---|---|---|
| 1 | 4 | Alternative investment fund managers | `3-alternative-investment-fund-managers` | 202 |
| 2 | 2 | Insurance companies | `51-insurance-companies` | 496 |
| 3 | 2 | Insurance Intermediaries | `137-insurance-intermediaries` | 1522 |
| 4 | 4 | Financial instruments market | `107-financial-instruments-market` | 204 |
| 5 | 4 | Financial holdings | `471-financial-holdings` | 3 |
| 6 | 4 | Investment service providers | `111-investment-service-providers` | 303 |
| 7 | 4 | Investment management companies | `1-investment-management-companies` | 76 |
| 8 | 4 | Crowdfunding service providers | `466-crowdfunding-service-providers` | 8 |
| 9 | 1 | Co-operative Credit Unions | `94-co-operative-credit-unions` | 20 |
| 10 | 1 | Credit institutions | `41-credit-institutions` | 425 |
| 11 | 1 | Payment service providers | `236-payment-service-providers` | 1110 |
| 12 | 4 | Pension Funds | `135-pension-funds` | 14 |
| 13 | 4 | Foreign exchange trading companies | `469-foreign-exchange-trading-companies` | 15 |
| | | | **TOTAL** | **4398** |

### Template fields (fixed — do not derive these at runtime)
`RegCtry = 'LV'`, `RegCode = 'CBOL'`, `ListCode = '1'…'13'`. These are the three tokens of
`<CC> <AGENCY> <listnr>`: the **two-letter country code**, the **agency code alone**, and the
**bare ListNr**. Not `'Latvia'`, not `'LV CBOL'`, not `'LV CBOL 1'`. The writer asserts all
three before saving.

Lists overlap by design — an entity can sit in several segments (e.g. a bank appears in
both list 10 and list 11, an AIFM in both list 1 and list 6). Nothing is deduped: the
register's own row count per list is the truth, and QA counts against the site.

### ListLabel reasoning
House rule: `1` = bank, `2` = insurance, `3` = both, `4` = everything else.
- **2 (insurance)** — lists 2 and 3.
- **1 (bank)** — lists 9 (credit unions), 10 (credit institutions), 11 (payment services).
- **4 (other)** — funds, holdings, instruments market, pension funds, FX, crowdfunding.

**List 11 is the one soft call, and it got softer in v4.** When it was 44 hand-picked rows
built around the Banks sub-segment, `1` was clearly right. Taken whole it is 1110 rows
dominated by e-money / payment institutions and EEA passporting entities, so `4` is
arguable. Left at `1` (unchanged from the last delivery) — flag for the requester.

### RegulationType
All 4398 rows are `Regulated`. **Liquidation / suspension status is deliberately not
covered** (user instruction, 2026-09-02): the segments are taken exactly as the ticket
defines them and no status sub-segment is fetched, flagged, or subtracted. Note this means
the 5 entities in `169-credit-institutions-in-liquidation` (ABLV Bank, Baltic International
Bank, Latvijas Krājbanka, …) are inside list 10's 425 and carry `Regulated` like every
other row. If that is not wanted, it is a one-line change — see "Judgment calls".

Of the five not-in-good-standing sub-segments that exist on the register, only that one is
non-empty; `151-insurance-companies-in-liquidation`, `152-insolvent-insurance-companies`,
`159-provision-of-services-suspended` and `155-provision-of-payment-services-suspended` all
return **0 results** as of 2026-09-02.

---

## Site quirks (things that will break this later)

1. **`?limit=N` silently caps a page at 1000.** This is the big one, and it is why v3's
   fetch strategy could not survive the ticket change. `?limit=5000&segments=137-insurance-
   intermediaries` returns **HTTP 200 with exactly 1000 rendered rows** while `resultCount`
   still says 1522. No error, no truncation notice. v3 got away with a single-shot
   `limit=5000` only because its sub-segment filtering kept every list under 1000; the
   moment lists 3 and 11 went whole, that same call would have quietly lost 632 rows.
   v4 requests `limit=1000` and pages.
2. **`?page=N` is honoured and is the only pagination that works.** Measured: `limit=1000
   &page=1` → 1000 rows, `page=2` → 522, `page=3` → 0, summing to the declared 1522 with no
   overlap. `limit=500` paginates cleanly too. But `start=` / `offset=` / `p=` /
   `limitstart=` are **silently ignored and return page 1 with HTTP 200** — a soft-404 trap
   that would produce the first page repeated forever.
3. **The page loop must not stop on "we have enough".** It stops on a short/empty page only,
   so that the reconciliation against `resultCount` is an independent check. A loop that
   halts once it reaches the declared count can never report a mismatch.
4. **The old site is gone.** Every `uzraudziba.bank.lv/en/market/*` URL from the original
   ticket 301-redirects to one landing page on `www.bank.lv`. Two different old URLs return
   byte-identical HTML.
5. **`?format=json` is the stable way in.** Returns `resultCount`, `results`,
   `childSegments` and `tags`. `results`/`childSegments` are HTML *fragments*, not
   structured data, so BeautifulSoup is still needed. `limit=0` is **not** "unlimited" — it
   drops the `results` key and will `KeyError`.
6. **Duplicate names are real rows, not a bug.** List 3 renders 1522 rows over 1518 distinct
   names — four personal names appear twice as separate registrations. Never dedupe.
7. **Row-level status is invisible.** An entity in `169-credit-institutions-in-liquidation`
   renders its info-items as `['Credit institutions', 'Reg. Nr. 50003149401', 'Latvia']` —
   the liquidation status appears nowhere on the listing row. Anyone who later wants to
   flag those rows must fetch the status sub-segment separately and match on reg nr; it
   cannot be read off the parent fetch.
8. **Latvian diacritics.** Names carry ā č ē ģ ī ķ ļ ņ š ū ž. Title matching goes through
   NFKD accent-strip + NFKC + lowercase — never `==`.
9. **Excel eats registration numbers.** `40003764029` becomes `4.000376e+10` unless the ID
   columns are pinned to text before `to_excel`. Handled, and the script now reads the
   workbook back and asserts no ID came back as a float. Do not remove that block.
10. **Segment ids are numeric and unstable across renames** (`1000-latvian-investment-
    management-companies` sits next to `1-investment-management-companies`). v4 uses the
    ticket's aliases verbatim as the requester asked, but still reads the landing page each
    run and prints `*** ALIAS DRIFT ***` if the live link for that segment title no longer
    matches the ticket. All 13 matched on 2026-09-02.

No Cloudflare, no JS rendering, no Selenium. Plain `requests` + BeautifulSoup with
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
| `RegCtry` | `'LV'` (fixed) |
| `RegCode` | `'CBOL'` (fixed) |
| `ListCode` | bare ticket ListNr, `'1'`…`'13'` (fixed) |
| `ListLanguage` | `'EN'` |
| `ListProcessDate` | `now.strftime('%Y-%m-%d')` |

**Empty by design:** `Address_1`, `City`, `Zip`, and licence dates — see judgment call 2.

**3948 of 4398 rows have an empty `InternalID_1`, and that is correct.** Verified by
country: **100%** of the 327 Latvian rows carry a registration number, versus 3% of the
4071 foreign rows. The register lists EEA passporting entities (freedom of establishment /
freedom to provide services) without a Latvian reg nr. The proportion jumped from v3's
16% empty purely because v4 includes those EEA entities, which the old sub-segment
selection filtered out. Top countries: Germany 491, Austria 465, France 464, Latvia 327,
Ireland 250, Luxembourg 249.

---

## Built-in checks

The run fails loudly rather than shipping a bad file:

- per-list `reconciled: site declares N / parsed N`, or `*** MISMATCH ***`, plus a
  `lists reconciled: 13/13` line in the summary
- `*** ALIAS DRIFT ***` if a ticket alias no longer matches the live landing page
- schema assert: columns are exactly the fixed 43-key `sqldict`
- **template-field assert** — `RegCtry` is exactly `LV`, `RegCode` is exactly `CBOL`, and
  every `ListCode` is a bare number. An earlier revision shipped `RegCode` empty and
  `ListCode` as `'LV CBOL 1'`; this assert is why that cannot happen again
- **Name-content assert** — a row count alone does not prove the Name column holds names
  (a sibling regulator once reconciled perfectly with `Name` full of `Yes`/`No`), so the
  script asserts separately that no Name is blank or a stray flag value, and prints the
  distinct-name count
- **Excel round-trip assert** — the workbook is re-read after writing and `InternalID_1` is
  checked for float coercion

---

## Judgment calls for the requester

1. **`ListLabel` for list 11** — `1` vs `4`; see reasoning above. Left at `1`.
2. **`Address_1` / `City` / `Zip` and licence dates are empty.** Detail pages carry legal
   address and per-licence valid-from dates but are **~1.1 MB each**. At v3's 460 entities
   that was ~500 MB; at 4398 it is roughly **4.8 GB** and a very long run. `parse_detail()`
   is implemented and working behind `FETCH_DETAIL = False` — flip one flag, no rewrite
   needed. Requester decides whether the address is worth the cost.
3. **Liquidation entities are included and marked `Regulated`** (see RegulationType above).
   Deliberate, per instruction. Say the word and they can be excluded or given their own
   RegulationType.
4. **The register exposes a 14th segment, `202-crypto-asset-market`**, that the ticket does
   not mention. Not scraped. Likely worth a follow-up ticket.

---

## Running

```bash
python3 LV_CBOL_v4.py
```

Writes `LV CBOL SQL Ready <YYYY-MM-DD HH.MM.SS>.xlsx` (sheet `SQL Ready`) into this
folder — not `tempfolder/`. Runtime ~1 min. The notebook `LV_CBOL_v4.ipynb` is generated
from the `.py` via the `#---- Begin_<name> ----` markers and holds byte-identical code.
