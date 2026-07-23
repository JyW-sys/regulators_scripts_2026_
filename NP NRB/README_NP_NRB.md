# NP NRB — Nepal Rastra Bank

- **Jira:** DECD-5812 (epic DECD-3438, Regulators 2026 – Internal Crawlers)
- **Source site:** https://www.nrb.org.np
- **Language:** English
- **RegCtry / RegCode:** NP / NRB
- **RegulationType:** Regulated

## Lists (from Jira ticket)

| ListNr | ListName | URL | Notes |
|---|---|---|---|
| 2 | List of Banks and Financial Institutions | https://www.nrb.org.np/category/list-of-bfis/?department=bfr | Open the most recent "BFI's List in English" and extract all entities |

## Status
- [x] v1 scraper built — `NP_NRB_v1.py` (2026-07-01)
- [x] Validated vs source PDF — 121 entities: 106 licensed BFIs (A:20, B:17, C:17, D:51,
      Infra:1) + 15 "Others" (Cooperative:1, Hire Purchase:10, Representative Offices:3, Hydropower:1)

## Implementation notes (v1)
- Landing page lists dated "BFI's List in English (Mid <Month> <Year>)" releases; the scraper
  picks the newest by (year, month). That link 302-redirects straight to a PDF.
- PDF parsed with pdfplumber `find_tables()`; rows assigned to a class by matching each row's
  y-position to the nearest class header above it, **carried across page breaks** (Class D spills
  onto a later page before its next header).
- Class → ListLabel: A/B/Infrastructure = 1 (banks), C/D = 4 (other).
- `Date of Operation` → RegulationDate (ISO). Head Office → Address_1 + City (last comma part).

## "Others" section (now INCLUDED, per ticket owner, 2026-07-01)
- Parsed from the last page below "Others:" — a different **4-visible-column** layout
  (S.No | Name | Office | Contact Office), handled by the `layout="others"` class defs:
  - **A. Cooperative** (1) — Rastriya Sahakari Bank → CoType "Cooperative", ListLabel 1
  - **B. Hire Purchase** (10) → "Hire Purchase Company", ListLabel 4
  - **C. Representative Offices** (3) — foreign banks (Mashreq/Doha/ICICI); `Office` is the
    foreign HQ → City + mapped Cntry (UAE→AE, Qatar→QA, India→IN); Nepal contact → Address_2;
    CoType "Representative Office", ListLabel 1
  - **D. Hydropower Investment & Development** (1) — HIDCL → ListLabel 4
  For Others rows, `Office` → Address_1/City, `Contact Office` → Address_2. No dates in this section.
- ListLabel for Cooperative & Representative Offices set to 1 (banks); Hire Purchase & Hydropower = 4.
- One source-side date artifact preserved as-is: *Infinity Laghubitta* shows `1900-01-09` in the PDF.
