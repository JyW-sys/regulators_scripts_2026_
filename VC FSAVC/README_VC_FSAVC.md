# VC FSAVC

## Regulator Information

- **Country/Region Code**: VC
- **Regulator Code**: FSAVC
- **Full Name**: Financial Services Authority of St. Vincent and the Grenadines
- **Website**: https://fsasvg.com/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6325

## Script

- **Current Version**: `VC_FSAVC_v2.py`
- **Approach**: 8 plain WordPress pages (LiteSpeed cache). Plain `requests` with a desktop User-Agent and `verify=False` returns HTTP 200 with full content for every URL — no Cloudflare/WAF challenge encountered, so **DrissionPage was not needed**. Parsed with BeautifulSoup.

### v2 changes (vs `VC_FSAVC_v1.py`)

1. **ListNr 4 contact-block bug (the defect in the v1 output file).** v1 only read a following `<p>` for the address/`Tel:`/`Fax:`/`Email:` block. 4 of the 15 entities publish their contact block inside a `<div class="tb_text_wrap">` (Elementor text-editor widget, `<br>`/`<div>`-separated lines) instead of a `<p>` — *Lex Mercatoria Fiduciary Ltd.*, *GOLD IN (ST. VINCENT) CO., LTD.*, *CARIBBEAN TRUST COMPANY LTD*, *ST. VINCENT TRUST AND ESCROW LTD*. v1 emitted those 4 rows with empty `Address_1`/`City`/`Phone`/`Fax`/`Email`/`Website` and this README wrongly recorded it as "no contact block on the page". v2 accepts both shapes → **15/15** contact blocks.
2. **Phone labels widened.** Those `<div>` blocks use `Office Land Line:` and `Mobile Contact:` rather than `Tel:`, so fixing (1) alone would still have lost the number. v2 captures `Tel`/`Telephone`/`Phone`/`Office Land Line`/`Mobile Contact`/`Mobile`/`Cell`, joining multiple numbers with `" / "`.
3. **Tables selected by header text instead of positional index.** v1 used `tables1[0]`, `tables2[:6]`, … — a hard-coded index silently yields wrong data the day the source inserts or removes a table. v2 drops fee/rate schedules by header (`Fee`, `Asset Size`, `Class of License`, `Statutory Deposit`) and dispatches each entity table on its own header row.
4. **Per-list expected row counts asserted at the end** of the run, so a structural change on the source fails loudly instead of passing QA.

Row counts (180), `ListLabel`, `License_Type`, `RegCtry`/`RegCode`/`ListLanguage`/`ListCode` and the ListNr 1 Sales-Representatives decision are **unchanged** from v1 — all were re-verified row-by-row against the live pages and match the source exactly. The only cells that differ between the v1 and v2 outputs are the 4 ListNr 4 contact blocks above (`Address_1` 4, `City` 4, `Phone` 4, `Email` 4, `Fax` 1, `Website` 2).

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | List of Insurance Companies, Intermediaries and Pension Fund Plans Operating in St. Vincent and the Grenadines | https://fsasvg.com/licensed-insurance-and-pension-plans-2/ | Extract the entities from the different tables of Insurances. |
| 2 | Mutual Funds in St. Vincent and the Grenadines | https://fsasvg.com/mutual-funds/ | Extract the entities from the different table of funds. |
| 3 | International Banks In St. Vincent and the Grenadines | https://fsasvg.com/international-bank-list/ | NEW LIST! Extract the entities from the two tables. |
| 4 | List of Registered Agents/Trustees/Service Providers | https://fsasvg.com/registered-agents-and-trustees-service-providers/ | NEW LIST! Extract the entities under "Currently Registered Agents/Trustees/Service Providers:" |
| 5 | Credit Unions in St. Vincent and the Grenadines | https://fsasvg.com/credit-union/ | NEW LIST! Extract the entities from the table. |
| 6 | Licensed Building Societies in St. Vincent and the Grenadines | https://fsasvg.com/building-societies/ | NEW LIST! Extract the entities from the table. |
| 7 | Friendly Societies in St. Vincent and the Grenadines | https://fsasvg.com/friendly-societies/ | NEW LIST! Extract the entities from the table. |
| 8 | Microfinancing Institutions in St. Vincent and the Grenadines | https://fsasvg.com/money-services-businesses/ | NEW LIST! Extract the entities from the table under "Microfinancing Institutions" |

## Page structure & parsing

Every page is an `<h2>`/`<h3>`-headed WordPress article containing one or more HTML `<table>`s; most pages also carry a **fee-schedule table** (application/annual/renewal fees) at the end, which is always out of scope and excluded by taking only the entity tables in document order.

- **ListNr 1** has 11 tables total. The first 8 are entity tables (Registered Pension Plans; Motor & General Insurance Companies; Long Term Insurance Companies; Insurance Agents; Insurance Brokers/Adjusters/Association of Underwriters; International Insurance Companies; International Insurance Intermediaries; Insurance Sales Representatives); the last 3 are fee schedules and are skipped. The "Insurance Sales Representatives" table is 2-column (`Insurance Company | Sales Representative(s)`, the latter a comma-separated list of individual people) — the entity being registered is the **insurance company**, so `Name` is taken from column 1; the sales-representative names in column 2 are not captured anywhere in the schema (no "represents" field exists), same information-loss tradeoff as the Insurance Agents table below.
- **ListNr 2** has 7 tables; the first 6 share the same 3-column shape (`Name of Mutual Fund(...) | Type of Mutual Funds | Status`) and are unioned; the 7th ("Fee Schedule: Mutual Funds") is skipped.
- **ListNr 3** has 2 tables: active licensed international banks (`International Bank | License Class | Address | Main Contact`) and banks under liquidation (`International Bank Under Liquidation | Class | Liquidator`).
- **ListNr 4** is *not* a table — under the "Currently Registered Agents/Trustees/Service Providers:" heading the page alternates `<h5>`/`<h4>` entity-name headings with a contact block (address / `Tel:` / `Fax:` / `Email:` / `Web:`). **The contact block is a `<p>` for 11 entities and a `<div class="tb_text_wrap">` for the other 4** (see v2 changes above); both are accepted. The site footer tagline is also a `<p>`, so a block only counts when it carries a `Tel:`/`Email:`/`Fax:`/`Web:`-style label. The walk stops at the "Quick Links"/"Useful Links" footer headings, which sit immediately after the last real entity in the DOM.
- **ListNr 5** takes only the "Name of Credit Union" table; the asset-size fee-schedule table is skipped.
- **ListNr 6** takes the single "Building Societies" table (1 entity).
- **ListNr 7** takes the "Name of Society | Name of Society (Continued)" table, which is laid out as **two name columns side by side** purely to fit the page — both columns are flattened into individual entity rows. The fee table is skipped.
- **ListNr 8**: per the Jira Comments, only the table located directly under the `<h2>Microfinancing Institutions</h2>` heading is extracted; the two Money Remitter agent/sub-agent tables (MoneyGram, Western Union) on the same page are explicitly out of scope for this ListNr and were not scraped.

### Contact-field parsing

Several free-text blobs pack `Tel:`/`Fax:`/`Email:`/`Web:`/`Contact:` labels back-to-back in one string (e.g. list3's Address/Main Contact cells, list4's per-entity `<p>`). A shared regex stop-lookahead (`Tel:|Fax:|Email:|Web(site)?:|Contact:`) prevents one label's value from bleeding into the next. For list3's active banks, Phone/Fax/Zip are taken from the bank's own **Address** cell (its official number), while the **Main Contact** cell (a named individual, e.g. "Contact: Dianne Samuel") is preserved verbatim in `Address_2` rather than overwriting the entity's own phone; Email falls back to the Main Contact cell only if the Address cell has none. For banks under liquidation, no street address is published at all, so the **Liquidator**'s contact block is placed in `Address_2` (prefixed `"Liquidator: ..."`) and its Phone/Email populate the entity's Phone/Email fields as the only available contact channel.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | first column of each entity table, or heading text (list4); for list1's Sales Representatives table, the **Insurance Company** column (col 1), not the individual Sales Representative names (col 2) |
| License_Type | table-specific label (e.g. `Motor & General Insurance Company`, `Mutual Fund Manager`, `International Bank (Class B)`, `Credit Union`, `Friendly Society`, `Microfinancing Institution`) — see per-list breakdown below |
| Address_1 / Address_2 / City / Zip | parsed from address/contact free text where present (lists 3 & 4 only); `City="Kingstown"` when the text mentions it; `Zip` matches an `VC####` postal-code token |
| Phone / Fax / Email / Website | regex-parsed from `Tel:`/`Fax:`/`Email:`/`Web:` labels (lists 3 & 4 only) |
| Cntry | `VC` |
| RegulationType | `Regulated` for all in-force entities; `Under Liquidation` for the 2 international banks explicitly listed as "Under Liquidation" (ListNr 3) |
| ListName | Jira `ListName`, verbatim |
| ListLabel | assigned per ListNr — see table below |
| ListLanguage | `EN` (source is entirely in English) |
| RegCtry / RegCode | `VC` / `FSAVC` |
| ListCode | Jira `ListNr` |
| ListProcessDate | run date (`datetime.date.today().isoformat()`) |

### ListLabel judgment calls

| ListNr | ListLabel | Reasoning |
|---|---|---|
| 1 | 2 (insurance) | Dominated by insurance companies/agents/brokers; the pension-fund-plan rows are grouped in with it since there is no dedicated "pension" ListLabel |
| 2 | 4 (other) | Mutual funds are neither a bank nor insurance list |
| 3 | 1 (bank) | International banks |
| 4 | 4 (other) | Registered agents/trustees/corporate-service providers — neither bank nor insurance |
| 5 | 1 (bank) | Credit unions are deposit-taking cooperatives, treated as bank-like per project convention |
| 6 | 1 (bank) | Building societies are deposit-taking mutuals, treated as bank-like |
| 7 | 2 (insurance) | Friendly societies are member mutual-aid/benefit societies providing insurance-like (sickness/death) benefits |
| 8 | 4 (other) | Microfinancing institutions are neither a traditional bank nor an insurer |

## Notes / QA

**Row counts** (180 total, greenfield — no `qa_positive_combined/` baseline exists yet):

| ListCode | Rows | Notes |
|---|---|---|
| 1 | 97 | 34 pension plans + 14 motor/general insurers + 7 long-term insurers + 16 agents + 12 brokers/adjusters/underwriters + 2 international insurers + 2 international intermediaries + 10 insurance companies with registered sales representatives |
| 2 | 42 | union of 6 mutual-fund tables; all `Status=Active` |
| 3 | 4 | 2 active international banks + 2 under liquidation (a 3rd liquidation row was a blank spacer `<tr>` and correctly dropped) |
| 4 | 15 | all headings under "Currently Registered Agents/Trustees/Service Providers:", stopping before the footer "Quick Links"/"Useful Links"; all 15 now carry a parsed contact block |
| 5 | 4 | credit unions |
| 6 | 1 | single building society |
| 7 | 13 | 8 + 5 names flattened from the two-column table |
| 8 | 4 | microfinancing institutions only, per Jira scope (Money Remitter agent tables excluded) |

**Non-empty rates** (v2): `Name`/`Cntry`/`License_Type`/`RegulationType`/`ListLanguage`/`ListProcessDate` 100% (180/180). `Address_1` 17/180, `City` 17/180, `Phone` 18/180, `Email` 19/180, `Fax` 11/180, `Website` 9/180, `Zip` 2/180 — populated only for ListNr 3 (Address_1 2/4 — the 2 banks under liquidation have no street address published, only a liquidator contact; Phone 3/4; Email 4/4) and ListNr 4 (**15/15** in v2, was 11/15 in v1). This is a real reflection of the source: lists 1, 2, 5, 6, 7, 8 are simple name-only registries with no address/phone/email published anywhere on their pages.

**Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` — clean, no hits.

**Duplicates within the same ListCode** (6 rows, all legitimate, not parsing bugs):
- *Pan American Life Insurance Company of the Eastern Caribbean Ltd.* and *St. Vincent Insurances Ltd.* (ListNr 1) each appear twice: once under their primary category (Long Term / Motor & General Insurance Company) and once under Insurance Sales Representative(s) — the same company is both a licensed insurer and has its own registered sales force, a legitimate dual entry, not a bug.
- *St. Vincent Building and Loan Association* (ListNr 1) appears twice: once as sponsor of its own staff pension plan, once as an Insurance Agent representing Guardian Life/Guardian General — a legitimate multi-role entity, the same pattern documented in `PG BPNG`.
- Several other Sales Representative(s) companies are the same entity as a Motor & General/Long Term insurer under a slightly different name string on the source itself (e.g. "G.T.M Life Insurance Company Limited" vs. "GTM Life Insurance Company Limited"; "Gulf Insurance" vs. "Gulf Insurance Limited") — not deduplicated since the strings genuinely differ on the source, left as-is per project convention.

**Judgment calls / limitations**:
- ListNr 1's "Insurance Sales Representatives" table is `Insurance Company | Sales Representative(s)` (10 companies, each with a comma-separated list of individual reps). The entity being registered is the **insurance company**, so `Name` = column 1 (company); the individual sales representative names in column 2 are not captured anywhere in the schema (no "represents" field exists) — a documented information loss, not a bug. (An earlier version of this scraper incorrectly split column 2 into 84 individual-person rows; corrected per user feedback to collect the company instead.)
- ListNr 1's Insurance Agents table similarly drops the "Insurance Company Represented" column for the same reason (there, the entity being registered is the individual agent, so `Name` = the agent's own name).
- No non-English content encountered — the entire site is in English, so no translation was required.
