# VU RBV

## Regulator Information

- **Country/Region Code**: VU
- **Regulator Code**: RBV
- **Full Name**: Reserve Bank of Vanuatu
- **Website**: https://www.rbv.gov.vu/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6326

## Script

- **Current Version**: `VU_RBV_v1.py`
- **Approach**: plain `requests` (desktop UA, `verify=False`) returns HTTP 200 for every page on this site — no Cloudflare/WAF challenge, so **no DrissionPage is needed**. The site is a Joomla CMS: each list URL is a Joomla "article" whose body is parsed with BeautifulSoup.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Deposit Taking Institutions | https://www.rbv.gov.vu/.../authorised-banks-supervised-financial-institutions?view=article&id=74:deposit-taking-institutions&catid=2 | Extract all entities under this list, click on each entity's hyperlink for details |
| 2 | Other Financial Institutions | ...&id=75:other-financial-institutions&catid=2 | Extract all entities under this list, click on each entity's hyperlink for details |
| 3 | Insurance | ...&id=76:insurance-companies-and-intermediaries&catid=2 | Open each category and extract all entities under each link, click on each entity's hyperlink for details |
| 5 | Credit Unions | ...&id=423:credit-unions&catid=2 | NEW LIST! Extract all entities under this list, click on each entity's hyperlink for details |
| 6 | Payment Service Providers | ...&id=427:payment-service-providers&catid=2:uncategorised | NEW LIST! Extract all entities under this list, click on each entity's hyperlink for details |

Note: the Jira description has no ListNr 4 — that is not a gap in this scrape, the ticket simply skips that number.

## Page structure & parsing

Each ListNr's article contains one or two levels of navigation before reaching an actual entity:

- **ListNr 1** (id=74) has two `<strong>`-labelled sections, each followed by its own `<table>`:
  - "Domestic Banks" → a table of **3 sub-category links** (Vanuatu Owned Banks / Subsidiaries of Foreign Banks / Branches of Foreign Banks), each of which is itself opened to reach the actual bank entities (1 / 3 / 0 respectively — "Branches of Foreign Banks" currently lists no bank at all, just a one-line note).
  - "International Banks" → a table of **9 entity links directly** (no further nesting).
- **ListNr 2** (id=75) and **ListNr 5/6** (id=423, id=427) are a single `<table>` of entity links directly — no category layer.
- **ListNr 3** (id=76, Insurance) is two levels deep: the page lists **8 category links** (Insurance Managers, Insurance Agents, Insurance Brokers, Captive Insurance, External Insurance, International Insurers, Local Insurance Companies, Reinsurer); each category page is opened in turn to reach its entities. A ninth heading, "Protected Cell Companies", currently has no companies under it (no link at all) and is correctly skipped.
- Every entity name — at every level — is a hyperlink to its own small Joomla "contact" article, which the scraper opens for Address/Phone/Fax/Email/Website, per the Jira comment "click on each entity's hyperlink for details".

**Detail pages are hand-typed free text, not a consistent template.** Labels ("Address", "Telephone", "Facsimile", "Email", "Website", plus job titles like "Director", "Resident Director", "Country Head", "Contact Person", "Chief Executive Officer" ...) appear with `:`, `-`, `–`, or split across two text nodes (label on one line, value on the next, sometimes with a stray lone `:` line in between). `parse_detail_page()` implements a small line-based state machine:

1. Get the body's text split on Joomla's own line breaks (`<p>`/`<br>` boundaries), strip a leading `:`/`-`/`–` off every line (Joomla often puts the punctuation on the value's own line, not the label's).
2. Classify each label-looking line by **keyword** (`address` → Address, `phone`/`tel`/`telephone` → Phone, `fax`/`facsimile` → Fax, `email` → Email, `website`/`web site` → Website) rather than an exhaustive fixed list, since job titles vary a lot; anything containing a person/company-title keyword (`director`, `manager`, `chairman`, `ceo`, `contact`, `company`, `person`, `head`, ...) is recognised and its value discarded (no field for contact-person name in the fixed schema).
3. A recognised label with no inline value waits for the next non-punctuation line as its value; unrecognised plain lines default to the Address bucket (safe fallback for the many entities with no explicit "Address:" label at all, e.g. the addresses are just bare lines before "Telephone:").
4. Email/Website values are validated (must contain `@` / a `.`) and a whole-page regex fallback is used if the line-parser came up empty or wrong — this recovers real emails from a couple of pages with broken inline `<a>` markup (see Notes/QA).
5. A line that is exactly "Port Vila" (the most common city on this site) is pulled out of the address into `City`; other cities (e.g. Sydney, Auckland, Suva) are left inside `Address_1` since a generic city extractor wasn't worth building for a handful of foreign addresses.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | entity link text on the list/category page |
| License_Type | the section/category the entity was found under (e.g. "Vanuatu Owned Banks", "International Banks", "Insurance Agents", "Credit Union") |
| Address_1 | free-text address lines from the entity's detail page (see parser above) |
| City | `Port Vila` when an address line matches exactly; blank otherwise |
| Phone / Fax / Email / Website | parsed from the entity's detail page; `;`-joined if a page lists more than one (e.g. two directors' contacts) |
| Cntry | `VU` for every row — follows the project convention of the regulator's own jurisdiction (see PW PFIC / UG IRAUG), even for the small number of Insurance Brokers/External Insurance entities whose `Address_1` shows they are actually headquartered in Australia or New Zealand |
| RegulationType | `Regulated` |
| ListLabel | `1` for ListNr 1 (banks); `2` for ListNr 3 (insurance); `4` for ListNr 2, 5, 6 (mixed/other — matches the `SC CBSEY` precedent of labelling Credit Unions and Payment Service Providers as `4`, not `1`) |
| ListLanguage | `EN` |
| RegCtry / RegCode | `VU` / `RBV` (from the folder name) |
| ListCode / ListName | Jira ListNr / ListName verbatim |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **Total 54 rows**, matching Jira exactly: ListNr 1 = 13, ListNr 2 = 3, ListNr 3 = 32, ListNr 5 = 3, ListNr 6 = 3.
- Non-empty rates: Name 54/54, Cntry 54/54, Address_1 53/54, Phone 48/54, Fax 19/54, Email 50/54, Website 18/54, City 37/54. The gaps are genuine — several insurance entities (e.g. *EverBest Re Corporation Ltd*, *TGM Insurance Ltd*) simply don't publish a phone/email/website on their detail page, and *Island Experience Vanuatu*'s detail page has no address at all (only a mobile contact number). Fax and Website are inherently sparse on this site — most entities just don't have one.
- No encoding red flags (`Ã©|â€™|Â |Ã¯|\?{3,}`) found.
- **One legitimate duplicate `Name`**: *National Bank of Vanuatu* appears once under ListNr 1 (Vanuatu Owned Banks) and once under ListNr 3 (Insurance Agents) — the site links these to two distinct detail-page URLs (`id=88` bank contact vs `id=109` "...Contact (insurance company)"), i.e. NBV genuinely holds two separate licenses. Not a parsing bug.
- Several other near-duplicates are **not** flagged by exact-name matching but are worth calling out: *Credit Corporations Vanuatu Limited* (ListNr 2) and *Credit Corporation Vanuatu Ltd* (ListNr 3, Insurance Agents) are almost certainly the same company under two license categories (name spelled slightly differently on the two detail pages); *Willis New Zealand* (ListNr 3, Insurance Managers) and *Willis New Zealand Limited* (ListNr 3, Insurance Brokers) likewise. *Jeffery Gete*, *Sanma Luganville Public Land Transport Committee*, and *Vancare Insurance Ltd* (all ListNr 3, Insurance Agents/Local Insurance Companies) share the same phone/email — these read as individually-licensed named insurance agents operating out of the same underlying insurer's office, a common pattern for small-island agent registries, not a scraping error.
- **Known minor parsing artifacts** (accepted rather than special-cased, given the source pages are hand-typed and inconsistent):
  - *Pacific Private Bank Limited* (ListNr 1): its detail page has malformed markup that splits the word "Director" mid-word (`<strong>Resident Directo</strong>r: ...`), so the fragment `Resident Directo, r:` leaks into `Address_1`.
  - *Capital Insurance Ltd* (ListNr 3): its Website value is split across two lines (`www.cig.com.pg` / `/vanuatu`); only the first line is captured as Website and the continuation `/vanuatu` leaks into `Address_1`.
  - *Atlas Insurance Broker Ltd* (ListNr 3): the source page has its own typos ("Postal Addrss:", "Telepone:") that aren't recognised as labels, so those two label words leak into `Address_1` (the actual phone number is still captured correctly elsewhere on the page).
- `Cntry` is `VU` for all 54 rows per the documented project convention (see Field mapping above) — a handful of Insurance Brokers/Captive Insurance/External Insurance entities are actually headquartered in Auckland (NZ) or Sydney (AU) per their `Address_1`; this is visible in the data rather than encoded into `Cntry`.
- Language: all source pages are in English; no translation was needed.
- No `qa_positive_combined/` baseline exists for this regulator — greenfield.
