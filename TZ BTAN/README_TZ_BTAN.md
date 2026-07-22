# TZ BTAN

## Regulator Information

- **Country/Region Code**: TZ
- **Regulator Code**: BTAN
- **Full Name**: Bank of Tanzania
- **Website**: https://www.bot.go.tz/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6302

## Script

- **Current Version**: `TZ_BTAN_v1.py`
- **Approach**: `requests` + `BeautifulSoup` for the HTML list; `requests` + `pdfplumber` for the two PDF lists (both are text-extractable — no OCR needed). `verify=False` for the corporate TLS proxy. A small `get()` retry helper wraps every request because `bot.go.tz` is a slow/flaky host (intermittent proxy/read timeouts).

## List Types

| ListNr | ListName | Source | ListLabel | Count |
|--------|----------|--------|-----------|-------|
| 1 | List of Licensed Institutions | HTML tabs @ `/BankSupervision/Institutions` | 1 | 52 |
| 2 | List of Licensed Tier 2 Microfinance Service Providers | PDF (46 pp) | 4 | 3138 |
| 3 | List of Approved Digital Lending Platforms | PDF (3 pp) | 4 | 19 |
| | | | **Total** | **3209** |

### List 1 — Licensed Institutions (HTML)

`https://www.bot.go.tz/BankSupervision/Institutions` renders one Bootstrap tab-pane per institution category. Every pane **except `nav-BureauDeChange`** is parsed (the ticket says *skip the Bureau de Change filter* — 174 rows excluded). The pane/category name is stored in **CoType**:

| Category (CoType) | Count |
|--|--|
| Commercial Bank | 35 |
| Development Finance Institutions | 2 |
| Financial Leasing Company | 4 |
| Regional Town Municipal | 2 |
| Regional Town Municipal Outside Reginal Capital | 1 |
| Mortgage Re-Financing Company | 1 |
| Microfinance Banks | 5 |
| House Financing Company | 1 |
| Regional Town Council | 1 |

Each row's contact cell mixes `Tel:` / `Fax:` / `email:` — these are regex-split into Phone / Fax / Email; the physical-location cell → Address_1.

### List 2 — Tier 2 Microfinance Service Providers (PDF)

`https://www.bot.go.tz/Other/Orodha ya Watoa Huduma Ndogo za Fedha wa Daraja la Pili.pdf`
Columns: `S/No. | NAME | PHYSICAL ADDRESS | POSTAL ADDRESS | DISTRICT | REGION | TELEPHONE NUMBER | E-MAIL ADDRESS | LICENCE NUMBER`.

### List 3 — Approved Digital Lending Platforms (PDF)

`https://www.bot.go.tz/Other/REGISTER OF LIST OF APPROVED DIGITAL LENDING PLATFORMS.pdf`
Columns: `S/N | NAME OF THE LICENSED MSP | DIGITAL LENDING PLATFORM | HOSTING ENVIRONMENT | PHYSICAL ADDRESS | TELEPHONE NUMBER | E-MAIL ADDRESS`. Name = the licensed MSP (the regulated entity); the platform name is kept in **Typology**.

## Field mapping

| sqldict field | List 1 | List 2 | List 3 |
|---------------|--------|--------|--------|
| Name | institution name | NAME | NAME OF THE LICENSED MSP |
| CoType | tab category | — | `Digital Lending Platform` |
| Typology | — | — | digital lending platform name |
| Address_1 | physical location | PHYSICAL ADDRESS | PHYSICAL ADDRESS |
| Address_2 | — | POSTAL ADDRESS | — |
| City | — | DISTRICT | — |
| Phone | `Tel:` | TELEPHONE NUMBER | TELEPHONE NUMBER |
| Fax | `Fax:` | — | — |
| Email | `email:` | E-MAIL ADDRESS | E-MAIL ADDRESS |
| InternalID_1 (`Licence Number`) | — | LICENCE NUMBER | — |
| Cntry | `TZ` | `TZ` | `TZ` |
| RegulationType | `Regulated` | `Regulated` | `Regulated` |
| RegCtry / RegCode / ListCode | TZ / BTAN / 1 | TZ / BTAN / 2 | TZ / BTAN / 3 |
| ListLanguage | EN | EN | EN |
| ListProcessDate | run date (`%Y-%m-%d`) | " | " |

## Notes / QA

- **3209 entities**, no empty names.
- **List 1 ListLabel = 1** (bank/deposit-taking institutions register). It also contains a few non-bank finance categories (leasing, mortgage, housing); if BVD prefers a mixed label, change to 4. Bureau de Change is excluded per ticket.
- **List 2 — excluded 41-row REVOKED/UPGRADED annex.** The PDF ends with a second table whose schema is `… REGION | LOCAL/FOREIGN | STATUS | LICENCE NUMBER`, where STATUS ∈ {REVOKED, UPGRADED}. These are status-change records (no longer active Tier-2 licensees), so they are **not** included in this positive list. They are detected by `col6 ∈ {LOCAL, FOREIGN}` and counted in the run log. **Confirm** whether BVD wants them captured separately (e.g. as cancellations).
- **List 2 City = DISTRICT** (finest locality the register provides, e.g. TEMEKE, KWIMBA); REGION is left in the postal address. 1 of 3138 rows has no address/phone/email on the source.
- **List 3 Typology = platform name**; a couple of platform cells hold two space-separated names from PDF line-wrapping (e.g. `AIRPAY RAFIKI`) — review if platform must be atomic.
- No OCR used — both PDFs have a real text layer (`pdfplumber` extracts tables directly).
