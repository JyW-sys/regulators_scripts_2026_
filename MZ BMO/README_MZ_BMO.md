# MZ BMO

## Regulator Information

- **Country/Region Code**: MZ
- **Regulator Code**: BMO
- **Full Name**: Banco de Moçambique (Bank of Mozambique)
- **Website**: https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6332

## Script

- **Current Version**: `MZ_BMO_v2.py` (supersedes `MZ_BMO_v1.py`, whose output was rejected)
- **Approach**: plain `requests` (desktop UA, `verify=False`) against the licensing page — no Cloudflare/WAF challenge encountered, so DrissionPage was not needed. The page lists several dated `.xls` downloads under a "List of authorised institutions" `<h3>`; the scraper picks the file with the most recent **reference period** parsed from the link title ("… - Janeiro 2025"), then downloads it with `requests` (Referer header set) into `tempfolder/`.

### v1 → v2 changes

v1 produced the right 53 rows but the wrong content in two columns, which is why it was rejected:

1. **`Name` is now the original Portuguese, verbatim.** v1 machine-translated it into English, which destroyed proper nouns — "Cota Câmbios" → "Cota Exchange", "Caixa Mulher, Mcb, SA" → "Women's Fund, Microbank, SA", "Sociedade Interbancária de Moçambique" → "Interbank Company of Mozambique", "Mundo/Mundial Câmbios" → "World/Worldwide Exchange". The Jira ticket never asked for translation (its only comment is the download instruction), and the house convention for Portuguese/Spanish regulators (`ST BCSTP`, `ES BES`) is original-language `Name`.
2. **`Name - Mother Company` is now blank.** v1 filled it on all 53 rows with the Portuguese name; that column is reserved for a genuine parent company, and this source publishes no ownership data (`ES BES` populates it only for real parents).
3. **Download selection is by reference period, not publish date.** The site re-publishes old files — the 2021 list carries a *later* publish date (23-10-2024) than the 2023 list (9-10-2023 / 26-09-2024), so v1's publish-date sort could have selected a stale list once the Jan-2025 file ages.
4. **The sheet's own column-header row is skipped explicitly** instead of relying on it happening to sit above the first category header.
5. **City** from an explicit `Cidade/Vila/Distrito de X` marker is no longer restricted to a hard-coded gazetteer.
6. **Rows are emitted in Jira ListNr order** (1…9) rather than sheet order, and **`ListValidityDate` is derived** from the file's reference month instead of hard-coded.

## List Types

All 9 Jira lists turned out to be categories inside **one single Excel file** (`Relação das ICSF em Funcionamento — Janeiro 2025`, published 14-04-2025). Only ListNr 1's Jira row carries a URL/comment ("Download the most recent Excel file ... and extract the entities from each list under the listName category"); ListNrs 2–9 have no URL of their own because they are simply the other top-level section headers inside that same file's `Relação ICSF` sheet. This was confirmed by an exact 1:1 match between the 9 Jira `ListName` values and the 9 top-level section headers found in the sheet (down to shared typos, e.g. "Sociedades Finaceiras de Corretagem", and a Jira-only unaccented "Cartoes de Credito" that the script reproduces verbatim in `ListName`).

| ListNr | ListName (Jira, verbatim) | ListLabel | Rows |
|---|---|---|---|
| 1 | Bancos | 1 | 15 |
| 2 | Microbancos | 1 | 16 |
| 3 | Cooperativas de Crédito | 1 | 5 |
| 4 | Sociedades corretoras | 4 | 1 |
| 5 | Sociedades de Investimento | 4 | 1 |
| 6 | Empresas Prestadoras de Serviços de Pagamentos | 4 | 5 |
| 7 | Sociedades Finaceiras de Corretagem | 4 | 3 |
| 8 | Sociedades Emitentes ou Gestoras de Cartoes de Credito | 4 | 1 |
| 9 | Casas de Câmbio | 4 | 6 |
| | **Total** | | **53** |

## Page structure & parsing

The `Relação ICSF` sheet (columns: `Nr | Sigla | Nome da Instituição | Sede | Actividades`) is not a clean table — categories, sub-categories, and city/province groupings are all just extra rows mixed in with the data rows:

- A row is a **header/separator** whenever its `Nome da Instituição` cell is empty. Its label text sits in whichever of `Nr`/`Sigla` is non-empty (a data-quality quirk of the source: most category headers use the `Nr` column, but at least one uses `Sigla` instead — the parser checks both).
- **Top-level category headers** (`Bancos`, `Microbancos`, ... `Casas de Câmbio`) start a new `ListNr`/`ListName`.
- Under the payments section only, three **`Categoria de ...` sub-headers** (Electronic Money Institution / Payment Aggregator / Money Transfer Institution) set the `CoType` for that block.
- **`Cidade de X` / `Província de X` headers** set a running "current city" — used only as a fallback for entities whose own address text names no specific place (see City field note below).
- A **data row** has `Nr` (int), `Sigla` (optional abbreviation → `InternalID_1`), `Nome da Instituição` (entity name), `Sede` (one free-text blob mixing address + phone + fax + email-or-website in inconsistent Portuguese labels: `Telf:`, `Telefone:`, `Telef.`, `Tel:`, `Tel.:`, `Cel:`, `Celular:`, `Fax:`, `E-mail:`/`E- mail:`, and a combined `Telef./ Fax:` label), and (Bancos only) `Actividades` — multi-paragraph legal boilerplate identical for every bank, intentionally not mapped to any output field.

The `Sede` blob is split by a custom `parse_sede()` segmenter that locates each label by regex and slices the text between labels (rather than one all-in-one regex), because label order/presence varies row to row.

### City field — judgment call

City is derived four ways, in priority order:
1. An **explicit in-address settlement marker** — `Cidade de X` / `Vila de X` / `Distrito de X` — capturing **any** capitalised place token (v2; v1 only recognised places already listed in its gazetteer). This is checked first because it is an unambiguous, self-contained signal in the entity's own address text. A single token is captured because every multi-word place in this source ("Cabo Delgado") only ever appears as a section header, while a greedy multi-token capture would swallow the trailing `Telf`/`Tel` label.
2. A **bare gazetteer word match** anywhere in the address, used only if no marker phrase is present (e.g. a bare "Beira" or "Nacala" at the end of a street address with no "Cidade de" prefix).
3. An **in-address `Província de/do X` marker** — ranked *below* the bare gazetteer hit because a province is not a city, so a real town named elsewhere in the address should win (Servcred's `"Cidade de Lichinga, Província do Niassa"` → Lichinga, not Niassa).
4. Falls back to the **section's city/province header** (coarser — e.g. "Cabo Delgado"/"Sofala"/"Manica" province) only when the address text names no specific place at all.

The rank-3 demotion also fixes a v1 error: Confiança Mcb's address (`"Bela Vista, Rua Principal, distrito de Matutuine, Província de Maputo"`) was given City="Maputo" by v1, which reads as Maputo *city* ~100 km away; v2 returns the district actually named, "Matutuine".

Blank City is left blank rather than inferred from street names — seven entities (e.g. AC Microbanco, Banco BIG, Paytek) give only a street/building address with no locality anywhere in their row or section, and guessing "Maputo" from a well-known avenue would be fabricating data the regulator did not publish.

This ordering was tuned during QA: an earlier version used a bare gazetteer search with no marker-priority, which produced two kinds of error — (a) coarser results than necessary (e.g. a Nacala-based cooperative would get City="Nampula" from the province header instead of "Nacala" from its own address), and (b) one outright false positive, where "Nova Câmbios Moçambique"'s address (`"Manica Shopping Center, Loja 14, Cidade de Chimoio Tel: 25122782"`) matched the bare word "Manica" (part of the shopping mall's name, appearing earlier in the string) instead of the actual city "Chimoio" (named later via the explicit "Cidade de Chimoio" marker). Adding the marker-first check fixes this because "Manica" alone is not preceded by a `Cidade/Vila/Distrito/Província de` marker in that string, while "Chimoio" is.

## Language handling

- **`Name` is the original Portuguese, verbatim** — whitespace and comma spacing are tidied, nothing else. Source typos are preserved as published ("Acess Bank Mozambique, SA", "Metrolopolitano Microbanco, SA"), since the entity name must be matchable back to the regulator's own register.
- **`Name - Mother Company` is left blank.** The source publishes no ownership/parent data.
- **Address_1 is left in Portuguese.** Street/avenue addresses (`Av.`, `Rua`, `Bairro`, etc.) are not meaningfully translatable, and this is the form needed for postal use in Mozambique.
- **`ListLanguage = 'PT'`**, matching the precedent set by `ST BCSTP` (the project's other Portuguese-language regulator in this batch).
- `CoType` holds the **English** institution/category descriptor (e.g. "Bank", "Microbank", "Credit Cooperative", "Payment Aggregator") — a controlled vocabulary field, so it stays English exactly as `ST BCSTP` does alongside its Portuguese names; `License_Type` holds the **original Portuguese** category label from the sheet's own section header, to keep traceability back to the source wording.
- **`ListLanguage = 'PT'`**, matching the precedent set by `ST BCSTP` (the project's other Portuguese-language regulator in this batch).
- `CoType` holds the **English-translated** institution/category type (e.g. "Bank", "Microbank", "Credit Cooperative", "Payment Aggregator"); `License_Type` holds the **original Portuguese** category label from the sheet's own section header, to keep traceability back to the source wording.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | `Nome da Instituição`, original Portuguese verbatim |
| Name - Mother Company | *(blank — no ownership data published)* |
| InternalID_1 / InternalID_1_type | `Sigla` column / `"Sigla"` (when present) |
| CoType | English category/sub-category (payments section uses the `Categoria de ...` sub-header instead of the top-level category) |
| License_Type | original Portuguese section-header label (payments section appends the sub-category, e.g. `"Empresas Prestadoras de Serviços de Pagamentos – Payment Aggregator"`) |
| Address_1 | free-text portion of `Sede` before the first phone/fax/etc. label |
| City | see "City field — judgment call" above |
| Phone / Fax | parsed from `Sede`'s `Tel:`/`Telef:`/`Cel:`/`Fax:`/combined `Telef./Fax:` labels |
| Email / Website | parsed from `Sede`'s `E-mail:`/`E- mail:` label — classified as Email if it contains `@`, else Website (one row's `E-mail:` label is actually followed by a `www...` URL, not an address) |
| Cntry | `MZ` (regulator's own jurisdiction, per project convention — see `PW PFIC`) |
| RegulationType | `Regulated` |
| RegCtry / RegCode | `MZ` / `BMO` |
| ListCode / ListName | Jira `ListNr` / Jira `ListName` (verbatim, including its typos) |
| ListLabel | `1` for Bancos/Microbancos/Cooperativas de Crédito, `4` for the other 6 lists (see `KE CBK`/`RW NBRW` precedent for MFIs/credit cooperatives → 1) |
| ListLanguage | `PT` |
| ListValidityDate | end of the reference month parsed from the download's title — `2025-01-31` for "… - Janeiro 2025" (v1 hard-coded `2025-01-01`) |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

Greenfield regulator — no `qa_positive_combined/` baseline exists yet.

- **Total 53 rows** across all 9 ListCodes; per-list counts were re-verified row-by-row against the `Relação ICSF` sheet (82 raw rows = 1 title + 1 column header + 9 category headers + 8 city/province headers + 3 `Categoria de` sub-headers + spacers + **53 entities**) and match the table above. v1 also produced 53 — the row counts were never the defect.
- **Non-empty rates**: Name 53/53 (100%), Cntry 53/53 (100%), Address_1 53/53 (100%), RegulationType 53/53 (100%), ListProcessDate 53/53 (100%), CoType 53/53 (100%), License_Type 53/53 (100%), ListValidityDate 53/53 (100%), City 46/53 (87%), Phone 39/53 (74%), Fax 2/53 (4%), Website 1/53 (2%), Email 0/53 (0%), Name - Mother Company 0/53 (0%, by design).
  - Website/Email being near-zero was checked against the raw source rather than assumed: only **one** row in the entire sheet contains a `www...`/`@` token at all (Millennium BIM's `Sede`, which is itself labeled `E-mail:` but is actually a website URL — correctly reclassified as Website, not Email, since it has no `@`). This is a genuine source-data gap, not a parsing miss.
  - The 7 rows with blank City have address text naming no city/province at all (e.g. AC Microbank's `Sede` is only a street/building address with no locality mentioned anywhere in the row or its section).
- **Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` found **0** flagged cells across all columns — the legacy `.xls` reads its Portuguese diacritics (ç, ã, é, í, ó) cleanly via `xlrd`, unlike the ticket's warning about garbled PDF text extraction (not applicable here since the source is `.xls`, not PDF).
- **No duplicate Name values** — all 53 entity names are unique.
- **No blocked/skipped lists** — no anti-bot/WAF blocker was encountered on `bancomoc.mz` (plain `requests` with `verify=False` returned HTTP 200 immediately), and all 9 Jira lists were successfully extracted from the single source file.
- The `Actividades` column (present only for Bancos, containing identical multi-paragraph legal boilerplate for every bank) was deliberately not mapped to any field — it carries no per-entity information.
