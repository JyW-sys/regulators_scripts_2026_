# NA BNAM

## Regulator Information

- **Country/Region Code**: NA
- **Regulator Code**: BNAM
- **Full Name**: Bank of Namibia
- **Website**: https://www.bon.com.na/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6333

## Script

- **Current Version**: `NA_BNAM_v1.py`
- **Approach**: all 4 lists live on plain server-rendered ASP.NET HTML pages with no Cloudflare/WAF challenge — plain `requests` (with `verify=False` for the corporate TLS proxy on this Mac, and a desktop `User-Agent`) returns `200` directly for every URL. No DrissionPage/browser rendering was needed. Parsed with BeautifulSoup.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Authorised Banking Institutions | https://www.bon.com.na/Bank/Banking-Supervision/The-Banking-System-in-Namibia.aspx | Extract all entities under the subtitle: Authorised Banking Institutions |
| 2 | Authorised Dealers in Foreign Exchange | https://www.bon.com.na/Bank/Exchange-Control.aspx | Extract all entities under the subtitle Authorised Dealers in Foreign Exchange |
| 3 | Authorised Dealer in Foreign Exchange with Limited Authority (ADLA) | https://www.bon.com.na/Bank/Exchange-Control/Authorised-Dealer-in-Foreign-Exchange-with-Limited.aspx | Extract all entities under the subtitle: List of the licensed ADLAs: |
| 4 | Registered Credit Bureaus (NEW LIST) | https://www.bon.com.na/Bank/Banking-Supervision/The-Banking-System-in-Namibia.aspx | Extract all entities under the subtitle: Registered Credit Bureaus |

Lists 1 and 4 share the same source page (different `<h5>` sections on it).

## Page structure & parsing

- **List 1** (`The-Banking-System-in-Namibia.aspx`): an `<h5>Authorised Banking Institutions:</h5>` heading is directly followed (sibling) by a `<ul class="bon-custom-list">` where each `<li><a href="...">Name</a></li>` gives the bank name and its own corporate website. One entry, *Trustco Bank Namibia Limited*, is present in the page's HTML only as an `<!-- HTML comment -->` (i.e. the regulator has commented it out, not currently listed) — the scraper only walks live `<li>` tags so it is correctly excluded.
- **List 4** (same page): an `<h5>Registered Credit Bureaus</h5>` heading, same pattern, sibling `<ul class="bon-custom-list">` — but its two `<li>` entries are plain text with no `<a>` link (no website given for either credit bureau on this page).
- **List 2** (`Exchange-Control.aspx`): the string "Authorised Dealers in Foreign Exchange" also appears as a left-nav dropdown link and as a small `<h6>` related-content card title elsewhere on the page — the scraper disambiguates by requiring `<h5 class="section-title">` and excluding any heading also containing "Limited Authority" (which would otherwise match the ADLA nav heading fragment). The real content section is a Bootstrap card grid `<div class="row row-cols-lg-3">`; each card has an `<h6>` bank name and a "Visit Their Website" `<a>` button giving the URL.
- **List 3** (`Authorised-Dealer-in-Foreign-Exchange-with-Limited.aspx`): no `<ul>`/table at all — under `<h5 class="section-title">...(ADLA)</h5>` the names sit as raw text nodes separated by `<br/>` tags, between a `<strong>List of the licensed ADLAs:</strong>` marker and the next `<strong>Licensing Requirements Matrix...</strong>` marker. The scraper locates both `<strong>` markers among the section's direct children and collects the `NavigableString` text nodes between them, explicitly skipping `Comment` nodes (BeautifulSoup represents HTML comments as a `NavigableString` subclass, so a naive `isinstance(node, NavigableString)` check would wrongly include them). One entry, *Real Transfer Bureau de Change (Pty) Limited*, is HTML-commented out on the live page and is correctly excluded by this filter.

No address/phone/email is published for any of the four lists — only entity name, license category, and (for lists 1–2) a corporate website link.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | entity name text (from `<a>`, `<h6>`, or plain `<li>`/text-node, depending on list) |
| Website | linked corporate homepage where present (lists 1 & 2); blank for lists 3 & 4 (not published) |
| License_Type | the list's own descriptive label (e.g. "Authorised Banking Institution", "Registered Credit Bureau") |
| Cntry | `NA` (Namibia) |
| RegulationType | `Regulated` |
| ListName | Jira `ListName` verbatim, per ListNr |
| ListLabel | see judgment call below |
| ListLanguage | `EN` |
| RegCtry / RegCode | `NA` / `BNAM` |
| ListCode | Jira `ListNr` (1–4) |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **Row counts by ListCode**: List 1 = 7, List 2 = 6, List 3 = 4, List 4 = 2 → **19 rows total**. All match the number of live (non-commented) entries visually confirmed on each source page.
- **ListLabel judgment call** (per-ListNr, not a single blanket value):
  - List 1 (Authorised Banking Institutions) → `1` (bank).
  - List 2 (Authorised Dealers in Foreign Exchange) → `1` (bank) — the 6 entities are the same commercial/branch banks as List 1, just also licensed as FX dealers, not a distinct non-bank category.
  - List 3 (ADLA — Limited Authority) → `4` (other) — these 4 entities (Cambio Seguro, Casa de Cambio Forex, Interchange Money Exchange Namibia, Novacambios Namibia) are independent forex-exchange bureaus/money-changers, not licensed banks, so they don't qualify as a bank list.
  - List 4 (Registered Credit Bureaus) → `4` (other) — neither a bank nor an insurance list.
- **Duplicate names**: *Bank Windhoek Limited* and *Nedbank Namibia Limited* each appear twice — once under List 1 (Authorised Banking Institutions) and once under List 2 (Authorised Dealers in Foreign Exchange). This is a legitimate cross-list appearance (the same bank holds two separate authorisations), not a parsing bug — the two rows carry different `ListCode`/`License_Type` values.
- **Non-empty rates**: `Name` 100% (19/19). `Cntry` 100% (constant `NA`). `Website` populated for 13/19 (all of List 1 and List 2; blank for Lists 3 and 4 where the source publishes no website). `Address_1`/`Phone`/`Fax` are blank for all 19 rows — genuinely not published on any of the four source pages (name/website-only listings), not a scraping gap.
- **`Cntry = "NA"` reader gotcha**: Namibia's two-letter code is the literal string `"NA"`, which collides with pandas'/Excel's default "missing value" sentinel. Opening the output with `pandas.read_excel()` using default settings (or eyeballing in some BI tools) can make the `Cntry` column look blank/NaN even though the cell genuinely contains the text `NA`. Verified directly in the saved `.xlsx` (and by reading back with `keep_default_na=False`) that the cell value is correctly written as text `NA` for all 19 rows — flagging this here so a downstream reviewer doesn't mistake it for a missing-data bug.
- **Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` found 0 matches; the one accented name (*Banco Atlántico*) round-trips correctly.
- No `qa_positive_combined/` baseline exists yet for this regulator (greenfield).
- No blockers: all 4 Jira URLs resolved with plain `requests` (200 OK), no Cloudflare/WAF/CAPTCHA encountered, no DrissionPage fallback required.
