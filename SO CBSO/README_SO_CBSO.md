# SO CBSO — Central Bank of Somalia

- **Jira:** DECD-6293 (parent epic DECD-3438, Regulators 2026 — Crawlers)
- **RegCtry / RegCode:** SO / CBSO (maintenance site: `SO CBSO - Central Bank of Somalia`)
- **Scraper:** `SO_CBSO_v_1.ipynb` — requests + BeautifulSoup, no Selenium needed
- **Language:** English

## Lists

| ListNr | ListName | URL | ListLabel |
|---|---|---|---|
| 1 | Licensed Banks | https://centralbank.gov.so/licensed-banks/ | 1 |
| 2 | Licensed Money Transfer Businesses | https://centralbank.gov.so/licensed-money-transfer/ | 4 |
| 3 | Licensed Mobile Money Service Providers | https://centralbank.gov.so/mobile-money-service-providers/ | 4 |
| 4 | Licensed Microfinance Institutions (NEW LIST 2026) | https://centralbank.gov.so/licensed-microfinance-institutions/ | 4 |
| 5 | Licensed Takaful Operators (NEW LIST 2026) | https://centralbank.gov.so/licensed-takaful-operators/ | 2 |

## Site structure

All five pages share one Elementor/WordPress layout:

- One CSS grid `div.e-grid.e-con` per page; each direct-child `div.e-con` cell is one entity.
- Per cell: a logo image widget (`image.default`) plus an icon list (`icon-list.default`) with exactly 3 items, keyed by icon class: `e-fas-location-arrow` = address, `e-fas-globe` = website + email (in one span split by `<br>`, order varies), `e-fas-phone-alt` = phone.
- Plain `requests` works (UA header + `verify=False` for the corporate proxy). No pagination, no JS rendering, no Cloudflare.
- The bank's own contact block sits outside the grid, so scoping to the grid excludes it.

## Known caveats

- **Entity names are not published as text** — logos have empty `alt` attributes. `Name` is derived: logo filename → website domain → email domain. Names therefore need human review during validation (e.g. `www.agrobank.so` → "Agrobank").
- No license numbers, license dates, or separate city fields on the site. `City` is parsed from the tail of the address text (", Mogadishu, Somalia").
- Counts at first build (2026-07-20): 15 banks, 17 money transfer, 6 mobile money, 20 microfinance, 7 takaful = 65 total.
