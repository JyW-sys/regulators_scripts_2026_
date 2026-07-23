# BN AMBD Regulatory Lists

Monetary Authority of Brunei Darussalam (AMBD, since 2021 renamed Brunei Darussalam Central Bank, BDCB). All 6 lists come from the single "List of BDCB Licensees" register page, filtered by license type via GET params (`flt_sector[]` = whole sector, `flt_subs[]` = individual license types; the values are fixed ULIDs). `view=100` keeps each filtered list on one page; pagination (`page=N`) is handled as a safety net. The site is server-rendered (plain requests works, no Selenium) but drops connections on quick bursts — the scraper paces requests ~12s apart and retries with backoff.

Each licensee card: `<p class="h5default">Name</p>` + tagline `License Type | Sector` + accordion body with labelled blocks (Address / Business Address, Contact Details, Designated Head, Status, Individual Name, Principals, CIS Fund Distributor, Sub-Funds).

Jira: DECD-5885

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| BN | AMBD | 1 | Banks and Finance Companies | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees?search=&view=10 | Whole sector filter. Conventional/Islamic Banks + Conventional/Islamic Finance Companies. ~10 entities. |
| BN | AMBD | 2 | Takaful and Insurance | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees?search=&view=10 | Sub-filters only: Insurance Life/Non-life, Takaful General/Family, Corporate Agents, Brokers, Takaful Agents. Excludes the Individual Agents and Termination/Suspension filters (per ticket). Entities the register still shows under the selected filters are kept even if their card carries a Status note (confirmed with user — e.g. Halalan Toyyiban Insurance & Takaful Agency). ~62 entities. |
| BN | AMBD | 3 | Capital Market | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees?search=&view=10 | Just CMSL and CISL sub-filters (per ticket: no CMSRL, no Ceased*). CISL umbrella funds list Sub-Funds inside the card — sub-funds are NOT exploded into separate rows, only the licensed umbrella entity is kept. ~37 entities. |
| BN | AMBD | 4 | Payment System Operators | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees?search=&view=10 | Whole sector filter. ~6 entities. |
| BN | AMBD | 5 | Specialised Market | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees?search=&view=10 | Whole sector filter: Money Changers, Money Remitters, Pawnbrokers. ~40 entities. |
| BN | AMBD | 6 | Others | https://www.bdcb.gov.bn/regulatory/list-of-bdcb-licensees | Whole sector filter: AML/CFT, Supervised by BDCB. ~2 entities. |

Field mapping: Name ← card title (always the company/agency name; "Individual Name" is just a detail field on agent cards), License_Type ← tagline first part, Address_1 ← Address/Business Address, Phone/Fax/Email/Website ← parsed from Contact Details. No license numbers published → InternalID left empty. RegulationType = 'Regulated'.
