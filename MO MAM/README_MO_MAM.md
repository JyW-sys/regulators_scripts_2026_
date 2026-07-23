# MO MAM — Monetary Authority of Macao (AMCM)

Scraper for Macao's financial regulator, **AMCM** (amcm.gov.mo), English content.

- **Jira:** DECD-6135 (parent epic DECD-3438 — Regulators 2026 Crawlers)
- **RegCtry:** `MO`
- **RegCode:** `MAM` (confirmed on the regulators maintenance site)
- **RegulationType:** `Regulated`
- **Script:** `MO MAM_v_1.ipynb`
- **Output:** `MO MAM SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`), saved in this folder
- **Run:** plain `requests` — **no browser needed.** The site is a Vue SPA whose page URLs
  return an empty shell; all data (including the "+" accordion details from the ticket) comes
  from one unauthenticated JSON API call per list:
  `GET https://www.amcm.gov.mo/api/v1.0/cms/companies?slug=<SLUG>` with header
  **`Api-Language: en`** (omitting the header silently returns Chinese). The `?type=` param in
  the site URLs equals the API `slug` 1:1. `verify=False` for the corporate TLS proxy.

## Lists (ticket ListNr → API slug(s))

| ListNr | `ListName` (ticket) | `ListLabel` | Slug(s) | Count (2026-07-13) |
|---|---|---|---|--:|
| 1 | Banks incorporated in Macau | 1 | bank-leaf-1 | 12 |
| 2 | Branches of banks incorporated overseas | 1 | bank-leaf-2 | 19 |
| 3 | Macao Postal Savings (Caixa Económica Postal) | 1 | bank-leaf-3 | 1 |
| 4 | Finance companies | 4 | other-institution-1 | 1 |
| 5 | Other Financial Institutions | 4 | oi-3/-4/-9/-7/-8/-6/-2 (7 subsections) | 31 |
| 6 | Insurance Institutions | 2 | insurance-1/-2/-3/-5 (4 subsections) | 34 |

(slugs abbreviated; full form `company-parent-<slug>`)

Per-subsection counts: list 5 = Remittance 4, Money changers 10, Financial leasing 7,
Financial asset trading 2, Payment services 4, Securities intermediaries 3, Others 1;
list 6 = Life 13, General 14, Insurers & Intermediaries Associations 6, Representative Offices 1.

## Field mapping / decisions

- API record fields: `company` → `Name`, `address` → `Address_1`, `tel` → `Phone`,
  `fax` → `Fax`, `email` → `Email` (**`mailto:` prefix stripped**; a bare `"mailto:"` = empty),
  `website` → `Website` (nullable).
- **Subsection title → `CoType`** for lists 5 and 6 (the ticket requires collecting per
  subsection; the API has no heading inside the payload, so attribution is by slug).
- `data.updatedAt` per slug (site's "last revision") → `ListValidityDate`.
- `branch` values of the form **"Head Office: <place>"** (overseas insurers/banks) →
  `Cntry - Mother company` as ISO-2 (Bermuda/Canada/Hong Kong/Macau/P.R.C./USA mapped;
  anything new is kept verbatim). Plain "Head Office" / "Macau Branch" values are not stored.
- The ticket's subsection bullet "Other Financial Institutions" under list 5 is a group header
  on the site nav — its members are the asset-trading/payment/securities/others slugs above.
- Not in ticket scope (deliberately skipped): forex-counter casinos (oi-5), investment fund
  management companies (oi-11), private pension funds (insurance-4), restricted licence bank
  (bank-leaf-4).
- Addresses keep Portuguese diacritics (ç, ã, º) — UTF-8, verified clean.

## Last run

- 2026-07-13 (v1): **98** entities. `MO MAM SQL Ready 2026-07-13 10.44.11.xlsx`.
