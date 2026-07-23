# KV BQK Regulatory Lists

Banka Qendrore e Republikës së Kosovës (BQK / CBK) — Central Bank of The Republic of Kosovo. All lists live in a single English-language PDF ("Lists of licensed/registered financial institutions") linked from one page. The PDF filename is date-stamped (e.g. `Lista-e-institucioneve-financiare-09.07.2026-ENG.pdf`), so the scraper discovers the link from the page at runtime instead of hardcoding it. The date in the filename is used as `ListValidityDate`.

Jira: [DECD-6109](https://moodysdatapipeline.atlassian.net/browse/DECD-6109)

| RegCtry | RegCode | ListNr | ListName | ListLabel | PDF section heading | Comments |
|---------|---------|--------|----------|-----------|---------------------|----------|
| KV | BQK | 1 | Commercial Banks | 1 | `Banks licensed` | |
| KV | BQK | 3 | Licensed Insurance Companies | 2 | `Insurers licensed` | |
| KV | BQK | 4 | Micro Finance Institutions | 4 | `MFIs registered` | |
| KV | BQK | 5 | Non Banks Financial Institutions | 4 | `NBFIs registered` | **Do not collect** entities under the sub-heading `NBFIs registered with the activity: Currency Exchange` (~65 exchange offices). |
| KV | BQK | 8 | Licensed Insurance Intermediaries | 2 | `Insurance brokers licensed` | **Do not collect** entities under `Individual Brokers in insurance` (~12 individuals). |
| KV | BQK | 9 | Pension Funds | 4 | `PENSION FUNDS` | |

Source page (all lists): https://bqk-kos.org/mbikeqyrja-financiare/institucionet-financiare-te-licencuara-2/?lang=en

## Scraper

- `KV_BQK_v2.ipynb` (current; `KV_BQK_v2.py` is the same code for the production machine) — requests + BeautifulSoup (PDF link discovery) + pdfplumber (text-layer PDF, no OCR needed), with a DrissionPage fallback for Cloudflare. `KV_BQK_v1.ipynb` is the requests-only first version.
- Flow: fetch page → find the PDF link by link text / filename pattern → download to `tempfolder/` → split text into sections by exact heading lines → split sections into numbered entity blocks (`N. Name`) → parse per-entity fields → fill `sqldict` → save xlsx to the regulator folder → clean `tempfolder/`.

## Production note (Cloudflare 403) — v2

- bqk-kos.org is behind **Cloudflare**. Plain `requests` works from some networks but gets **403 Forbidden** from the production Windows machine (IP/TLS-fingerprint block; richer headers don't help).
- v2 tries `requests` first; on any failure it logs `[WARN] ... falling back to DrissionPage (Cloudflare)` and re-fetches with **DrissionPage** (real Chrome, non-headless — the challenge doesn't clear headless), same pattern as `DO SSDO` / `CW CBCSCW`. The PDF is then downloaded **inside the browser** (`ele.click.to_download(...)`, CW CBCSCW pattern) because Cloudflare blocks requests' TLS fingerprint, not just the page URL.
- In the browser-rendered DOM the site JS appends `?lang=en` to the PDF href, so the link matcher strips the query string before the `.pdf` check — don't "simplify" that back to `endswith('.pdf')`.
- Production needs: Google Chrome + `DrissionPage` + `pdfplumber` (both packages are in root `requirements.txt`). A Chrome window opens briefly when the fallback triggers.
- Per-entity fields parsed from each block: name, street (`Address_1`), remaining address lines (`Address_2`), 5-digit zip + city, phone, fax, website, e-mail, and `Activity:` / intermediation-scope lines (stored in `License_Type`, mainly for NBFIs and bank intermediaries).

## Parsing quirks (as of 2026-07)

- The PDF section `Crypto-asset service operator (CASO) Licensed` is **not** in the ticket → skipped.
- Entity numbering in the PDF is unreliable (duplicate `12.` in NBFIs, duplicate `10.` in brokers, gaps) — the parser keys on the `N.` line pattern, not on sequence.
- List 8 contains one **unnumbered** entity right after the sub-heading "Brokerage and claims handling companies in insurance": *Insurance Claims Handling and Evaluation Company "ICM Co & Services"*. It is currently **collected** (it is not an individual broker); drop it if the ticket owner disagrees.
- Some banks appear again in List 8 as insurance intermediaries (TEB, NLB, BpB, BKT) — intentional, they hold both licenses.
- Entities marked `- In liquidation` in the PDF are kept with the marker in the name, `RegulationType = 'Regulated'` (still on the regulator's positive list). "Liquidator" contact-person lines are dropped from the address.
- Ziraat Bank's zip is printed as `110000` in the PDF (6 digits) — kept as printed.
- A few entities have no zip printed (Factor Leasing, Euro Broker, ALL SIG BROKER) — `Zip` left empty, `City` recovered from the "…, Kosovo" line.
