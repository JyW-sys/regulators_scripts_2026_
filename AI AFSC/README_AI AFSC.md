# AI AFSC — Anguilla Financial Services Commission

## Overview

Scraping pipeline for the Anguilla Financial Services Commission (AFSC) regulated-entities lists. The AFSC publishes six public "Regulated Entities" pages — one per sector — each containing one or more tables grouped by sub-typology (e.g. "Offshore Banks", "Domestic Insurers", "Insurance Brokers").

- **Country code:** AI (Anguilla)
- **Regulator code:** AFSC
- **Regulator selector value (Control Room maintenance page):** `AI AFSC`
- **Jira ticket:** [DECD-3438 parent → DECD-3826](https://moodysdatapipeline.atlassian.net/browse/DECD-3826)
- **Reporter comment:** existing Control Room code produces wrong template and is missing ListNr 6 (Credit Unions) — addressed in `AI AFSC_v_1.ipynb`.

## Source URLs & Typology

| ListNr | ListCode | ListName (ListName field)                 | URL                                                                                        |
|-------:|:--------:|--------------------------------------------|--------------------------------------------------------------------------------------------|
| 1      | 1        | Banking Regulated Entities                 | https://www.fsc.org.ai/banksre.php                                                         |
| 2      | 2        | Insurance Regulated Entities               | https://www.fsc.org.ai/insurancere.php                                                     |
| 3      | 3        | Company Management Regulated Entities      | https://www.fsc.org.ai/companymanagementre.php                                             |
| 4      | 4        | Mutual Funds                               | https://www.fsc.org.ai/mutualfundsre.php                                                   |
| 5      | 5        | Money Services Business Regulated Entities | https://www.fsc.org.ai/msbre.php                                                           |
| 6      | 6        | Credit Union Regulated Entities            | https://www.fsc.org.ai/crediture.php                                                       |

### Sub-typology (populated into the `Typology` SQL column)

Values are derived dynamically from each page's `<h3>`/`<h4>` sub-headings, e.g.:

- **Banking:** Offshore Banks
- **Insurance:** Domestic Insurers, Offshore Insurers, Captive Insurers, Insurance Managers, Insurance Brokers, Insurance Agents, Insurance Sub-Agents
- **Company Management / Mutual Funds / MSB / Credit Union:** sub-section titles as rendered on each page

## Field Mapping (AFSC table columns → SQL Ready schema)

| AFSC column                | SQL Ready column       |
|----------------------------|------------------------|
| Entity                     | Name                   |
| Street & Mailing Address   | Address_1 / Address_2  |
| Country (e.g. "The Valley, Anguilla B.W.I.") | City + Cntry (`B.W.I.` stripped, city = part before comma, Cntry defaults to `Anguilla`) |
| Tel                        | Phone                  |
| Fax                        | Fax                    |
| Email                      | Email (when present)   |
| Website                    | Website (when present) |
| License / Class / Type     | License_Type (when present) |

## Constant values

- `RegCtry = 'AI'`
- `RegCode = 'AFSC'`
- `ListCode` = last token of `reg` key (`'1'`..`'6'`)
- `RegulationType = 'Regulated'`
- `ListProcessDate` = today (YYYY-MM-DD)
- `ListName` = the `Typology` value for that list

## Runbook

1. Ensure dependencies: `pandas`, `requests`, `beautifulsoup4`, `openpyxl`, `lxml` (for `pd.read_html`).
2. Open `AI AFSC_v_1.ipynb`.
3. Run all cells top-to-bottom.
4. Output: `AI AFSC SQL Ready YYYY-MM-DD HH.MM.SS.xlsx` in this folder (single `SQL Ready` sheet).

## Notes / Known issues

- The AFSC pages are static HTML with standard `<table>` elements; no Selenium / JS rendering is required.
- A `seen_sections` set prevents duplicate parsing when a sub-typology heading appears on more than one page (rare but possible).
- Tables without an obvious "Entity / Name / Company / Licensee" header column are skipped (e.g. layout/contact tables).

## Version history

- **v_1** (2026-04-21): Initial template-compliant scraper. Covers all 6 ListNrs including Credit Unions (ListNr 6). Output schema matches the standard 43-column SQL Ready template.
