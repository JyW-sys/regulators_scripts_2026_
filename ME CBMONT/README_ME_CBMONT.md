# ME CBMONT — Central Bank of Montenegro

Scraper for Montenegro's central bank, **CBCG** (cbcg.me), English pages.

- **Jira:** DECD-6133 (parent epic DECD-3438 — Regulators 2026 Crawlers)
- **RegCtry:** `ME`
- **RegCode:** `CBMONT` (confirmed on the regulators maintenance site)
- **RegulationType:** `Regulated`
- **Script:** `ME CBMONT_v_1.ipynb`
- **Output:** `ME CBMONT SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`), saved in this folder
- **Run:** plain `requests` + `BeautifulSoup` + `pdfplumber`. No bot protection.
  `verify=False` is required — the corporate proxy re-signs TLS and certifi rejects its
  self-signed chain (curl works because it uses the system trust store).

## Lists (ticket ListNr → cbcg.me page; ticket skips ListNr 3 and 4)

| ListNr | `ListName` (ticket) | `ListLabel` | Count (2026-07-13) |
|---|---|---|--:|
| 1 | Register of Banks | 1 | 11 |
| 2 | Microcredit Financial Institutions (MFIs) | 4 | 12 |
| 5 | Leasing Companies | 4 | 1 |
| 6 | Factoring Companies | 4 | 2 |
| 7 | Companies for the Purchase of Receivables | 4 | 2 |
| 8 | Register of Payment Institutions | 4 | 7 |

## Site structure / parsing decisions

- **Lists 1, 2, 5, 6, 7:** entity links = `div.children-listing a.children-item` on each list
  page; each entity has a profile page. Profile fields are free-form
  `<strong>Label</strong>: value` paragraphs inside `main div.page-text`:
  - Name = `h1`; head-office address (label variants per type, banks use an en dash
    "Head–office") → `Address_1` + `City` (trailing ", Podgorica"-style token split off);
  - Licence No → `InternalID_1` (`InternalID_1_type = 'Licence No.'`);
  - Licence date → `RegulationDate`. **Three date formats occur** and are all handled:
    `of 18 December 2002`, `od 18 of December 2002` (Montenegrin "od"), `of 06.04.2015`.
  - Profiles publish **no phone/email/website** for lists 1–7 — those columns are empty by
    design there. Executive Director / board members have no sqldict field and are skipped.
- **List 8:** the list page's `div.table-responsive table` links go to **per-entity PDFs**
  (text-based, 1 page, parsed with `pdfplumber` — poppler not needed). Extracted: name (line
  after the "Registry of payment institutions" heading), street address + `ZIP CITY` line →
  `Address_1`/`Zip`/`City`, registration number → `InternalID_1` (`Registration No.`), contact
  phone/e-mail/internet address → `Phone`/`Email`/`Website`, decision date → `RegulationDate`
  (the date may sit 1–2 lines below the "Number and date of the Decision ON" label — the parser
  scans a 3-line window). PDF filenames are opaque/version-stamped — always taken from the page.
- The scraper prints a `[WARN]` for any profile/PDF with a missing address or id, so silent
  format drift shows up in the run log.
- 0.5 s sleep between entity fetches (~35 requests + 7 PDFs, ~1 min total).

## Last run

- 2026-07-13 (v1): **35** entities, 100% fill on Name / Address_1 / InternalID_1 /
  RegulationDate. `ME CBMONT SQL Ready 2026-07-13 10.36.58.xlsx`.
