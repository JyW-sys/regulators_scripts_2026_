# GD GARFIN Regulatory Lists

Grenada Authority for the Regulation of Financial Institutions (GARFIN) — Grenada's non-bank financial regulator. The public registers live under `https://garfin.gd/index.php/regulated-sectors`. Each sector page is built with the Joomla **SP Page Builder tabs** addon: every entity list is already present in the static HTML, just hidden behind a tab pane (`<a data-toggle="sppb-tab" href="#sppb-tab-...">`). No Selenium, JavaScript, or OCR is required — `requests` + BeautifulSoup reads the source directly.

Jira: [DECD-4819](https://moodysdatapipeline.atlassian.net/browse/DECD-4819) · Language: English · All entities marked `RegulationType = Regulated`.

| RegCtry | RegCode | ListCode | ListName | URL | Comments |
|---------|---------|----------|----------|-----|----------|
| GD | GARFIN | 1 | Credit Unions | https://garfin.gd/index.php/regulated-sectors/credit-unions | **REGISTERED CREDIT UNIONS** tab — collect all entities (10). |
| GD | GARFIN | 2 | Insurance Companies | https://garfin.gd/index.php/regulated-sectors/insurance | **REGISTERED COMPANIES** tab (general + long-term + Lloyd's = 26) **and** **BROKERS** tab (14) — combined into one list (40). |
| GD | GARFIN | 3 | Money Services Businesses | https://garfin.gd/index.php/regulated-sectors/money-services-businesses | **MONEY SERVICES BUSINESSES** tab — collect all entities (10). |
| GD | GARFIN | 4 | Pensions | https://garfin.gd/index.php/regulated-sectors/pensions | **REGISTERED PENSION PLANS** tab — collect only entities under the **Active** heading (46). Ignore the **Inactive** section. |

## Extraction notes

- **Tab matching:** the scraper finds each pane by matching the tab-nav link *text* (e.g. `REGISTERED CREDIT UNIONS`) rather than the volatile `sppb-tab-<timestamp>` id, so it survives the same page being rebuilt.
- **Pensions Active vs Inactive:** the pane holds two `<ol>` lists under `<strong>Active</strong>` / `<strong>Inactive</strong>` headings. The scraper anchors on the *Active* heading and takes the next `<ol>` only.
- **Encoding:** pages are UTF-8; entity names contain curly apostrophes (U+2019, e.g. *Lloyd's Underwriter*) and non-breaking spaces (U+00A0). The scraper forces `r.encoding='utf-8'` and normalizes `\xa0`/whitespace.
- **Names only:** these registers publish entity names with no address/ID/contact columns, so only `Name`, `ListName`, `RegCtry`, `RegCode`, `ListCode`, `Cntry` (Grenada), `ListLanguage` (English), `RegulationType` (Regulated) and `ListProcessDate` are populated.

## Output

`GD_GARFIN_v1.ipynb` → `GD GARFIN SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`).
Total expected: **106 entities** (10 + 40 + 10 + 46).
