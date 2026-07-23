# EE FSAEE — Finantsinspektsioon (Estonian Financial Supervision Authority)

Scraper for Estonia's financial regulator, **Finantsinspektsioon** (fi.ee).

- **RegCtry:** `EE`
- **RegCode:** `FSAEE`
- **RegulationType:** `Regulated`
- **Source:** fi.ee supervised-entity lists (English, **active** entities)
- **Script:** `EE_FSAEE_v2.py` / `EE_FSAEE_v2.ipynb` *(current/authoritative)*
- **Output:** `EE FSAEE SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`)

## What it collects

**v2 (current):** scrapes each of the 16 lists from its **own dedicated category URL** (see the
`REG` map in the script — taken from the prior scraper and validated). Each category page is a
paginated Drupal view (`?page=N`, ~100 rows/page; a page index past the end returns HTTP 404,
which is the stop signal). Some old category URLs `301`/meta-refresh to deeper current paths —
both are followed. Entities are the `.views-field-title a` hyperlinks; deduped per list by
`(name, href)`. This per-list method is more robust than v1's "group the combined page by `<h3>`
heading" approach, which mis-grouped 1 entity at a page boundary (list 10 = 438 vs the correct 439).

> **Detail pages carry no entity data.** On today's redesigned site, the page behind each entity
> hyperlink is a stub: its only contact block (`<li class="address/phone/email">`) is **the
> regulator's own HQ** ("Sakala 4, Tallinn 15030, +372 668 0500") repeated on every page — *not*
> the entity's address. The per-entity tables (Corporate Name, Commercial Registry Number, Address,
> Phone, …) that the previous Selenium scraper read **no longer exist**. So only `Name` + list
> membership is extractable; address-type columns are intentionally left blank.

## Lists (ticket ListNr → fi.ee category)

The ticket **skips ListNr 3** ("Representative offices of foreign credit institutions" — present
on the site but not requested). Each list maps 1:1 to a dedicated category URL (`REG` in the
script); the two looser ticket names (#11, #13) are pinned by those URLs, not guessed.
Counts are from the 2026-06-16 run.

| ListNr (`ListCode`) | `ListName` (ticket) | count | fi.ee category |
|---|---|--:|---|
| 1  | Licensed Credit Institutions in Estonia | 8 | licensed-credit-institutions-estonia |
| 2  | Affiliated Branches of Foreign Credit Institutions | 5 | affiliated-branches-foreign-credit-institutions |
| 4  | Providers of cross-border banking services | 452 | providers-cross-border-banking-services |
| 5  | Licenced Life Insurance Companies in Estonia | 2 | licenced-life-insurance-companies-estonia |
| 6  | Licenced Non-Life Insurance Companies in Estonia | 8 | licenced-non-life-insurance-companies-estonia |
| 7  | Affiliated Branches of Foreign Life Insurance Institutions | 3 | affiliated-branches-foreign-life-insurance-institutions |
| 8  | Affiliated branches of foreign non-life insurance institutions | 6 | affiliated-branches-foreign-non-life-insurance-institutions |
| 9  | Providers of cross-border life insurance services | 89 | providers-cross-border-life-insurance-services |
| 10 | Providers of cross-border non-life insurance services | 439 | providers-cross-border-non-life-insurance-services |
| 11 | List of Fund Management Companies | 12 | licenced-fund-management-companies |
| 12 | Cross-border Fund Management Companies | 72 | cross-border-fund-management-companies |
| 13 | Investment Firms | 6 | licenced-investment-firms-estonia |
| 14 | Providers of cross-border investment services | 684 | providers-cross-border-investment-services |
| 15 | Providers of Cross-border E-money Services | 263 | providers-cross-border-e-money-services |
| 16 | Estonian payment institutions | 9 | estonian-payment-institutions |
| 17 | Providers of Cross-border Payment Services | 316 | providers-cross-border-payment-**sevices** *(site typo)* |

## Notes / decisions

- **Active vs closed:** the ticket text says *"active supervised entities"* but the supplied URL
  ended in `?closed=1`. Per user decision the **active** set is scraped (no `?closed=1`).
- **Dedupe:** per list by `(Name, href)`.
- **No entity-level detail:** see the note above — the redesigned site's detail pages expose only
  the regulator's own contact block, so address/registry/phone are no longer available.
- **Run:** `python3 EE_FSAEE_v2.py` (no Selenium — plain `requests` + `BeautifulSoup`/`lxml`).

## Last run

- 2026-06-16 (v2): **2,374** unique entities across the 16 lists (per-list URL crawl).
