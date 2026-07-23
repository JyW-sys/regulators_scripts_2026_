# KM CBCO — Banque Centrale des Comores (BCC)

- **Jira ticket:** DECD-6108
- **Regulator:** Central Bank of the Comoros — https://banque-comores.km (French-language site)
- **Script:** `KM_CBCO_v1.ipynb`
- **RegCtry / RegCode:** `KM` / `CBCO`

## Lists

| ListNr | ListName | URL | Comments |
|---|---|---|---|
| 1 | Etablissements de credits | https://banque-comores.km/page/show/etablissements-de-credit | Collect all entities in bullet points under the heading: Etablissements de crédit |
| 2 | Intermédiaires financiers | https://banque-comores.km/page/show/intermediaires-financiers | Collect all entities in bullet points under the heading: Intermédiaires financiers |

## Approach

- Static pages — `requests` + `BeautifulSoup` (no Selenium needed). Browser `User-Agent` header, `verify=False` with `urllib3` InsecureRequestWarning suppressed.
- `response.encoding` is forced to `'utf-8'` so accented French renders correctly (no mojibake).
- The article body lives in `div.blog__details-left`; the target heading is the single `<h3>` inside it ("Etablissements de crédit" / "Intermédiaires financiers").
- Entities are the `<li>` items of the `<ul>` siblings **after** that `<h3>` (`heading.find_next_siblings('ul')`). This skips the page-meta `<ul>` (date/category) before the heading, plus all navigation, sidebar ("Sur la même rubrique") and footer lists.
- The `<h4>` blocks further down each page are descriptive prose about the same entities, **not** scraped (the bullet list is the authoritative enumeration per the ticket).
- Names are kept in French exactly as published (only whitespace collapsed and a trailing period stripped, e.g. `... (MCTV-SA).` → `... (MCTV-SA)`). Abbreviations in parentheses stay with the name. No address/phone appears in the bullets, so address fields are left empty.
- Per row: `Name`, `ListName` (Jira wording verbatim), `ListCode` (`1`/`2`), `RegCtry='KM'`, `RegCode='CBCO'`, `RegulationType='Regulated'`, `ListProcessDate=YYYY-MM-DD`. After each list the `bourange_same_length_array` helper pads `sqldict` to equal lengths.
- Output: `tempfolder/KM CBCO SQL Ready <timestamp>.xlsx`, sheet `SQL Ready`, empty names dropped.

## How to run

Run all cells of `KM_CBCO_v1.ipynb` (kernel working directory = the `KM CBCO` folder), or export the code cells to a `.py` placed in this folder and run it with the project Python. `tempfolder/` is created/emptied at start and receives the xlsx.

## Expected volume

Very small register (as of 2026-07): 7 entities in List 1 (4 banks + 3 IFD networks) and 3 in List 2 — 10 rows total. Both lists must be non-empty; a zero count on either list means the page structure changed.

## Caveats

- List 1 has **two** bullet lists under the heading (banks, then Institutions Financières Décentralisées); both are collected.
- The pages are static articles last edited Jan 2023; entity bullets on List 2 use slightly different long names than the `<h4>` prose below (e.g. "des Postes **et des** Services Financiers" in the bullet). The bullet wording is kept.
- List 2's last bullet ends with a period on the site; it is stripped from the name.
- If the site restyles (`div.blog__details-left` / `ul.ms-5` classes), the selectors need review — the scraper anchors on the container class and the `<h3>`.
