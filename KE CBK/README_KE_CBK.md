# KE CBK — Central Bank of Kenya

- **Jira ticket:** DECD-6106 "KE CBK"
- **Regulator:** Central Bank of Kenya (https://www.centralbank.go.ke)
- **Scraper:** `KE_CBK_v1.ipynb`
- **Output:** `tempfolder/KE CBK SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`, fixed 43-column schema)

## Lists

| ListNr | ListName | URL | Comments |
|---|---|---|---|
| 1 | Commercial Banks & Mortgage Finance | https://www.centralbank.go.ke/wp-content/uploads/2023/06/Directory-of-Licenced-Commercial-Banks-Authorised-NOHCs-June-2023.pdf | Extract all entities from this pdf |
| 2 | Licensed Money Remittance Providers | https://www.centralbank.go.ke/wp-content/uploads/2026/06/Directory-of-Licenced-Money-Remittance-Providers-June-2026.pdf | Extract all entities from this pdf |
| 3 | List of licensed Microfinance Banks | https://www.centralbank.go.ke/wp-content/uploads/2026/02/Directory-of-Licenced-Microfinance-Banks-Feb-2026.pdf | Extract all entities from this pdf |
| 4 | Licensed Forex Bureau | https://www.centralbank.go.ke/wp-content/uploads/2026/06/Directory-of-Licenced-Foreign-Exchange-Bureaus-June-2026.pdf | Extract all entities from this pdf |
| 5 | Licensed Credit Reference Bureaus | https://www.centralbank.go.ke/wp-content/uploads/2022/11/Directory-of-Licensed-CRBs-November-2022.pdf | Extract all entities from this pdf |
| 6 | Representative Offices of Foreign Banks in Kenya | https://www.centralbank.go.ke/wp-content/uploads/2025/07/Directory-of-Authorised-Representative-Offices-July-2025.pdf | Extract all entities from this pdf |
| 7 | Digital Credit Providers | https://www.centralbank.go.ke/wp-content/uploads/2026/04/Directory-of-Digital-Credit-Providers-April-2026.pdf | NEW LIST! Extract all entities from this pdf |

All 7 ticket URLs were live at build time (2026-07-09) — **no URL substitutions were needed**.

## ListLabel

Per ticket owner: 1 = bank named in list name, 2 = insurance, 3 = bank & insurance, 4 = other. Lists 1 (Commercial Banks), 3 (Microfinance Banks) and 6 (Representative Offices of Foreign Banks) = 1; lists 2, 4, 5, 7 = 4 (`ListLabeldict` in the notebook).

## Approach

All PDFs are downloaded with `requests` (browser User-Agent, `verify=False`, urllib3
InsecureRequestWarning suppressed) into `tempfolder/`, parsed with `pdfplumber`
(all pages), then deleted. All 7 PDFs are text-based — no OCR needed.

Two PDF layouts exist:

### A. "Profile block" directories — lists 1, 3, 5, 6, 7 (`parse_blob_pdf`)

Numbered entries (`1.` / `1 Name…`) followed by labelled lines
(`Postal Address:`, `Telephone:`, `Fax:`, `E-mail:`, `Website:`,
`Physical Address:`, `Date Licenced/Licensed/Authorised:` …).

- Page furniture is dropped line-by-line (CBK headers, `Page N of M`,
  `C2: CBK - Official`, bare page numbers, section titles).
- Entry starts are validated against the **expected running number** so that
  wrapped phone/address lines beginning with digits are never mistaken for a
  new entry. List 1 additionally allows the numbering to restart at `1.`
  because it has three sections (A: Commercial Banks 38, B: Mortgage Finance
  Institutions 1, C: Authorised Non-Operating Holding Companies 8 — all kept
  under ListCode 1).
- Each entry blob (multi-line cells joined) is sliced on a **whitelist** of
  known labels (longest-first, case-insensitive). Junk pseudo-labels inside
  addresses (`L.R. No:`, `Kenyatta Highway:`, `cc:`, `NB:`) are deliberately
  not in the whitelist, so they stay inside the address value.
- Name = text before the first label.

### B. 5-column tables — lists 2, 4 (`extract_tables`)

`No. | Name | Location | Contact Details | Date of Licencing` on every page.
Rows are kept only when column 0 is the running number (drops the repeated
title/header rows); multi-line cells are joined with spaces. The
`Contact Details` cell is split into postal address / Tel / Fax / Email /
Website with regexes (`parse_contact_cell`).

### Field mapping

| xlsx column | source |
|---|---|
| Name | entry name (kerning artifact `W akanda` → `Wakanda` fixed) |
| Address_1 | Physical Address (blob lists) / Location (table lists); falls back to postal |
| Address_2 | Postal Address / postal part of Contact Details |
| City | trailing city token of the postal (fallback physical/location) address |
| Zip | 5-digit Kenyan postal code from the postal address (kept as text, leading zeros preserved) |
| Phone / Fax / Email / Website | labelled values; email/website also regex-scanned as fallback |
| RegulationDate | `Date Licenced` / `Date Licensed` / `Date Authorised` — **raw as printed** (formats vary: `1916`, `8th January 1985`, `09.02.2010`, `April 10, 2026`) |
| RegulationType | `Regulated` |
| RegCtry / RegCode / ListCode | `KE` / `CBK` / `1`–`7` |
| ListName | Jira ListName verbatim (see table above) |
| ListProcessDate | run date `%Y-%m-%d` |

`InternalID_1` stays empty — none of the seven CBK directories publish licence
numbers, only licensing dates.

## How to run

Run all cells of `KE_CBK_v1.ipynb` top-to-bottom (global/venv Python with
`requests`, `pdfplumber`, `pandas`, `openpyxl`). `tempfolder/` is wiped and
recreated at start; the xlsx is written into `tempfolder/`. No Selenium, no
OCR required.

## Row counts (2026-07-09 run — 430 total)

| ListCode | ListName | Rows |
|---|---|---|
| 1 | Commercial Banks & Mortgage Finance | 47 (38 banks + 1 mortgage finance + 8 NOHCs) |
| 2 | Licensed Money Remittance Providers | 36 |
| 3 | List of licensed Microfinance Banks | 14 |
| 4 | Licensed Forex Bureau | 94 |
| 5 | Licensed Credit Reference Bureaus | 3 |
| 6 | Representative Offices of Foreign Banks in Kenya | 9 |
| 7 | Digital Credit Providers | 227 |

## Caveats

- **List 1 vintage:** the ticket URL is the June 2023 directory (latest one CBK
  publishes at a stable URL); lists 2–7 are 2022–2026 vintages per ticket.
- **PDF kerning artifacts:** the CBK PDFs' text layer sometimes inserts a
  stray space after the first letter (`W akanda`, `S hujaa`, `N AIROBI`).
  Fixed at the start of Name/Location cells and for `N AIROBI`; a couple of
  superscript-ordinal artifacts remain inside addresses (e.g. list 2
  `st Amal Plaza, 1 Avenue` = "Amal Plaza, 1st Avenue").
- Some entities legitimately have no phone (list 4), no website (most of
  lists 2/4/7) or no fax — those cells are simply empty in the source PDFs.
- If CBK replaces a PDF (they version the upload path by month/year), update
  the corresponding `regdict` URL; the parsers are layout-driven, not
  URL-driven.
