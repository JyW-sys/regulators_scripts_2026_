# TO NRBT

## Regulator Information

- **Country/Region Code**: TO
- **Regulator Code**: NRBT
- **Full Name**: National Reserve Bank of Tonga
- **Website**: https://www.reservebank.to/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6301

## Script

- **Current Version**: `TO_NRBT_v1.py`
- **Approach**: Static HTML, `requests` + `BeautifulSoup` (no browser needed). `verify=False` for the corporate TLS proxy.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Financial Institutions in Tonga | https://www.reservebank.to/index.php/financial-system/financial-institutions/financial-institutions-in-tonga | Single page, all entities extracted. |

## Page structure

Entities are `.fd-item` cards grouped under `h3.mod-title` section headings (no `<table>`). Each card exposes:

- `.fd-item-title` → **Name**
- `.fd-item-desc` → website link (`<a href>`) + address text + `Tel:` phone

The section heading is captured into **CoType**:

| Section heading | CoType | Count |
|-----------------|--------|-------|
| Commercial Banks | Commercial Bank | 4 |
| Licensed Foreign Exchange Dealers | Foreign Exchange Dealer | 27 |
| Licensed Moneylenders | Moneylender | 134 |
| **Total** | | **165** |

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | `.fd-item-title` |
| CoType | section heading (mapped) |
| Address_1 | `.fd-item-desc` text (Tel stripped out) |
| Phone | `Tel:` value parsed from the description |
| Website | first `http(s)` link in the description (banks only) |
| Cntry | `TO` |
| RegulationType | `Regulated` |
| ListName | Financial Institutions in Tonga |
| ListLabel | `4` — mixed list (banks + FX dealers + moneylenders, no insurance) → "everything else" |
| RegCtry / RegCode / ListCode | TO / NRBT / 1 |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **165 entities**, no duplicates.
- **ListLabel = 4**: the single page mixes commercial banks with non-bank FX dealers and moneylenders. If BVD prefers this treated as a bank list, change to `1`.
- Only commercial banks publish a website; FX dealers publish address + phone; moneylenders are name-only.
