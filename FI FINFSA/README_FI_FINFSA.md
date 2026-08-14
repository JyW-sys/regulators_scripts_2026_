# FI FINFSA

## Regulator Information

- **Country/Region Code**: FI
- **Regulator Code**: FINFSA
- **Full Name**: Finanssivalvonta — Finnish Financial Supervisory Authority (FIN-FSA)
- **Website**: https://www.finanssivalvonta.fi/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6744

## Script

- **Current Version**: `FI_FINFSA_v3.py` (supersedes `FI_FINFSA_v2.ipynb`)
- **Approach**: one public JSON API, no HTML parsing and no browser:
  `https://www.finanssivalvonta.fi/api/supervised-entity-api/v1/all-supervised-entities`
  queried with `Lang=2` (English) and **no group filter at all** — the whole
  register in a single call, with "Removed from the register" subtracted
  afterwards. `verify=False` for the corporate TLS proxy.
- **Selenium removed entirely** — v2 opened Chrome and then never used it.

### Why v3 exists

v2 crashed with **`KeyError: 'address'`**. The API restructured its payload: the
flat `address` / `zipCode` / `city` fields are gone and now live inside nested
arrays, and `telephone` / `wwwAddress` were removed with no replacement.

Measured against the live API on 2026-08-13 (not assumed) — a record's keys are:

```
groups, personsInCharge, supervisorsInFSA,
authorisationsAndOtherOperationGrounds, providedServices, funds,
principalOfAnAgent, tiedAgents, companyName, auxiliaryName, marketingName,
businessIdentityCode, homeState,
postalAddress, visitingAddress, headOfficeAddress, officeAddress
```

The four `*Address` keys are **arrays** of `{address, zipCode, city, country}`.
Coverage over the 961 in-scope records (an entity can publish more than one
block, so these overlap):

| block | records |
|---|---|
| `postalAddress` | 947 |
| `visitingAddress` | 246 |
| `headOfficeAddress` | 27 |
| `officeAddress` | 2 |
| none at all | 12 |

v3 resolves the address with a first-non-empty walk in that order.

### The stale group list — why v3 asks for nothing

**This is the important change.** v2 built the request from a hard-coded list of
121 group codes. That list returns **953** rows, but the register itself reports
**961** with "Removed from the register" unticked. The 8 missing entities sit in
two groups FIN-FSA created after v2 was written, so v2 never asked for them:

- **4989** — Foreign credit services' branches in Finland from EEA countries
- **4990** — Credit servicers

The 8 (each of them in *only* those groups):

| Name | InternalID_1 | group |
|---|---|---|
| Axactor Finland Oy | 1606758-4 | Credit servicers |
| CapFore Oy | 3430851-3 | Credit servicers |
| Intrum Oy | 1470246-8 | Credit servicers |
| Kredinor Oy | 2937875-2 | Credit servicers |
| Lowell Suomi Oy | 0140351-4 | Credit servicers |
| Lowell Suomi Oy (Lowell Danmark A/S) | FT ID 541 | Foreign credit services' branches |
| Myntro Collect Oy | 3126049-7 | Credit servicers |
| PRA Suomi Oy | 1569394-6 | Credit servicers |

Measured on the live API, 2026-08-13:

| call | rows |
|---|---|
| **no `Groups` parameter at all** | **1007** |
| v2's 121 codes | 953 |
| v2's codes + 4951 | 999 |
| v2's codes + 4989 + 4990 | **961** ← matches the site |
| **1007 minus the 46 entities whose only group is 4951** | **961** ← matches the site |

Appending 4989 and 4990 would fix today's count and go stale again the next
time FIN-FSA adds a category. So v3 sends **no `Groups` parameter**, which
returns the whole register, and drops the "Removed from the register" entities
in Python. That reproduces the site exactly and cannot rot.

v2's group list survives in the code as `KNOWN_GROUPS`, used for **nothing but
a printout**: any group in the payload that it does not list is reported at the
start of the run, so a new category is visible rather than silent. Today's run
prints 4989 and 4990.

Other v3 changes:

- **Group 4951 "Removed from the register" is excluded**, per the ticket. v2
  requested 4951 and then tagged those rows `RegulationType='Removed'`. v3 drops
  any record whose *only* group is 4951 — an entity that is also in a live group
  stays, which is how the site's own checkbox behaves. (Measured: 0 entities
  currently carry 4951 alongside another group, so today the rule removes
  exactly 46.)
- **`Phone` / `Website` are no longer emitted.** There is no replacement field
  in the new payload; writing them would have meant writing blanks.
- `businessIdentityCode` is JSON `null` for 123 entities. v2 compared against
  the **string** `'None'`, so it would have written the literal `None`.
- **`ListName` and `ListLanguage` filled** — v2 left both empty on every row.
- `scriptfolder` resolved per project convention (no hard-coded `C:\` path).
- `writer.save()` removed — pandas 2.x deleted `ExcelWriter.save()`.
- Non-schema `'Check'` column dropped from `sqldict`.

### Correction to an earlier diagnosis

An earlier note in this work claimed the API **silently caps responses at 999
rows**, on the evidence that one call returned 999 while a split returned
487 + 527 = 1014. **That diagnosis was wrong**, twice over. The 1014 counted
duplicates — the de-duplicated union of the split is exactly 999, identical to
the single call. And 999 was not a total either: it is simply what v2's stale
group list plus 4951 adds up to. The bare call returns **1007**, so there is no
cap at 999 and never was. The chunking that had been added to work around the
imagined cap has been removed.

## List Types

A single list. `ListLabel` left blank — pre-existing list, filled manually
downstream (user decision, 2026-08-13).

| ListNr | ListName | ListLabel | Source |
|--------|----------|-----------|--------|
| 1 | Supervised entities | *(blank)* | `all-supervised-entities` API, no group filter, group 4951 subtracted |

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | `companyName` |
| Typology | `groups[0].groupName` |
| License_Type | `authorisationsAndOtherOperationGrounds[].authorisationName`, joined |
| InternalID_1 | `businessIdentityCode` (`null` → empty, never the string `None`) |
| InternalID_1_type | `Business Identity Code` |
| Address_1 | first non-empty of `postalAddress` → `visitingAddress` → `headOfficeAddress` → `officeAddress`, field `address` |
| Zip / City | `zipCode` / `city` of the same block |
| Cntry | `homeState` |
| Phone / Website | **not emitted** — removed from the API |
| RegulationType | `Regulated` |
| RegCtry / RegCode / ListCode | `FI` / `FINFSA` / `1` |
| ListName | `Supervised entities` |
| ListLanguage | `EN` (the API is queried with `Lang=2`) |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Status / QA

- **Output**: `FI FINFSA SQL Ready 2026-08-13 16.56.00.xlsx`, **961 rows**,
  fixed 43-column schema (exact match for CLAUDE.md, no `Check` column),
  sheet `SQL Ready`.
- **961 matches the site exactly** — the register's own "Search results (961
  pcs)" with "Removed from the register" unticked. The script prints itself
  against that baseline, and against the 1007 whole-register figure, on every
  run.
- 1007 returned, 46 dropped as "Removed from the register" → 961.
- All **8** entities that the old group list was losing are present and carry a
  business identity code (verified by name in the output file).
- Fill rates: Name 961/961, Typology 961/961, Zip 903/961, Address_1 898/961,
  City 898/961, Cntry 952/961, InternalID_1 838/961 (the 123 `null` business
  identity codes), License_Type 674/961.
- `RegulationType` and `ListProcessDate` non-empty on all 961 rows;
  `ListProcessDate` is a single value, `2026-08-13`.
- No group-4951 entity present in the output (0 `Typology` values mention
  "Removed").

### Items needing your confirmation

1. **`Phone` and `Website` are now always empty.** The API no longer publishes
   them anywhere. If BVD needs them, they would have to come from a different
   source — flag it and I will look.
2. **`Cntry` is `homeState`**, i.e. the home *state* of the entity as the API
   reports it, not necessarily the country of the postal address. Confirm that
   is the wanted semantic.
3. **Group 4951 excluded** per the ticket — no `Removed`-flagged rows are
   produced at all. Confirm you do not want them retained with a cancellation
   status instead.
4. **The 8 credit-servicing firms are now included** (Intrum, Lowell, Axactor,
   PRA Suomi, Kredinor, CapFore, Myntro, plus the Lowell Danmark branch). They
   are on the register and the site counts them, so they are in — but they are
   debt collectors rather than banks or insurers. Say the word if BVD wants
   groups 4989 / 4990 held out of this list.

### Environment notes

- Global Python environment; `requests`, `pandas`, `openpyxl`. No browser.
- `verify=False` + `urllib3.disable_warnings` are required behind the corporate
  TLS proxy.
