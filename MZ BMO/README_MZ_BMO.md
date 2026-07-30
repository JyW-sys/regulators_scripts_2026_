# MZ BMO

## Regulator Information

- **Country/Region Code**: MZ
- **Regulator Code**: BMO
- **Full Name**: Banco de Moçambique (Bank of Mozambique)
- **Website**: https://www.bancomoc.mz/en/areas-of-expertise/licensing/licensing-of-institutions/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6332

## Script

- **Current Version**: `MZ_BMO_v1.py`
- **Approach**: plain `requests` (desktop UA, `verify=False`) against the licensing page — no Cloudflare/WAF challenge encountered, so DrissionPage was not needed. The page lists several dated `.xls` downloads under a "List of authorised institutions" `<h3>`; the scraper parses each download's date and picks the most recently published file, then downloads it with `requests` (Referer header set) into `tempfolder/`.

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

City is derived two ways, in priority order:
1. An **explicit in-address marker** — `Cidade de X` / `Vila de X` / `Distrito de X` / `Província de/do X` — matched against a 17-place Mozambique gazetteer. This is checked first because it is an unambiguous, self-contained signal in the entity's own address text.
2. A **bare gazetteer word match** anywhere in the address, used only if no marker phrase is present (e.g. a bare "Beira" or "Nacala" at the end of a street address with no "Cidade de" prefix).
3. Falls back to the **section's city/province header** (coarser — e.g. "Cabo Delgado"/"Sofala"/"Manica" province) only when the address text names no specific place at all.

This ordering was tuned during QA: an earlier version used a bare gazetteer search with no marker-priority, which produced two kinds of error — (a) coarser results than necessary (e.g. a Nacala-based cooperative would get City="Nampula" from the province header instead of "Nacala" from its own address), and (b) one outright false positive, where "Nova Câmbios Moçambique"'s address (`"Manica Shopping Center, Loja 14, Cidade de Chimoio Tel: 25122782"`) matched the bare word "Manica" (part of the shopping mall's name, appearing earlier in the string) instead of the actual city "Chimoio" (named later via the explicit "Cidade de Chimoio" marker). Adding the marker-first check fixes this because "Manica" alone is not preceded by a `Cidade/Vila/Distrito/Província de` marker in that string, while "Chimoio" is.

## Translation approach

Per the ticket's translation guidance, names are translated to English in `Name`, while the original Portuguese is preserved verbatim in `Name - Mother Company`. Since there is no clean generic/proper-noun split in Portuguese institution names, the approach taken is:

- **Descriptive institution-type words are translated** via an ordered, longest-phrase-first, word-boundary regex dictionary (`NAME_PHRASES`), e.g. `Banco` → `Bank`, `Microbanco` → `Microbank`, `Cooperativa de Crédito` → `Credit Cooperative`, `Casas de Câmbio` → `Exchange House`, `Sociedade Corretora` → `Brokerage Company`. Longer, more specific phrases (e.g. `Cooperativa de Crédito das Mulheres de` → `Women's Credit Cooperative of`) are matched before their shorter generic sub-phrases so a specific translation isn't clobbered by a generic one.
- **Brand/proper-noun parts are left as-is** (e.g. "BIM", "Standard Bank", "Letshego", "ABC", "FNB" style brand tokens are untouched); a few brand-adjacent words that recur across multiple entity names (e.g. "Moçambique" → "Mozambique", "Finanças" → "Finance") are also translated for consistency, since they function more like descriptive suffixes here than as a unique brand identifier.
- `Lda` (Portuguese "Limitada") is normalized to `Ltd` in the English name.
- **One documented source-file typo fix**: "Acess Bank Mozambique, SA" → "Access Bank Mozambique, SA" in the English `Name` only (the Portuguese `Name - Mother Company` keeps the source's own spelling, typo included).
- **Address_1 is left in Portuguese.** Street/avenue addresses (`Av.`, `Rua`, `Bairro`, etc.) are not meaningfully translatable and this is also the form needed for postal use in Mozambique — the same approach the ticket allowed ("translate address fields where practical"; judged not practical/useful here).
- **`ListLanguage = 'PT'`**, matching the precedent set by `ST BCSTP` (the project's other Portuguese-language regulator in this batch).
- `CoType` holds the **English-translated** institution/category type (e.g. "Bank", "Microbank", "Credit Cooperative", "Payment Aggregator"); `License_Type` holds the **original Portuguese** category label from the sheet's own section header, to keep traceability back to the source wording.

## Field mapping

| sqldict field | Source |
|---|---|
| Name | `Nome da Instituição`, English-translated (see above) |
| Name - Mother Company | `Nome da Instituição`, original Portuguese |
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
| ListValidityDate | `2025-01-01` (source file titled "Janeiro 2025") |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

Greenfield regulator — no `qa_positive_combined/` baseline exists yet.

- **Total 53 rows** across all 9 ListCodes; per-list counts match the table above and sanity-check against the Jira 9-list structure (1 list, 1 downloadable file, 9 categories inside it).
- **Non-empty rates**: Name 53/53 (100%), Cntry 53/53 (100%), Address_1 53/53 (100%), City 46/53 (87%), Phone 39/53 (74%), Fax 2/53 (4%), Website 1/53 (2%), Email 0/53 (0%).
  - Website/Email being near-zero was checked against the raw source rather than assumed: only **one** row in the entire sheet contains a `www...`/`@` token at all (Millennium BIM's `Sede`, which is itself labeled `E-mail:` but is actually a website URL — correctly reclassified as Website, not Email, since it has no `@`). This is a genuine source-data gap, not a parsing miss.
  - The 7 rows with blank City have address text naming no city/province at all (e.g. AC Microbank's `Sede` is only a street/building address with no locality mentioned anywhere in the row or its section).
- **Encoding check**: regex `Ã©|â€™|Â |Ã¯|\?{3,}` found **0** flagged cells across all columns — the legacy `.xls` reads its Portuguese diacritics (ç, ã, é, í, ó) cleanly via `xlrd`, unlike the ticket's warning about garbled PDF text extraction (not applicable here since the source is `.xls`, not PDF).
- **No duplicate Name values** — all 53 entity names are unique.
- **No blocked/skipped lists** — no anti-bot/WAF blocker was encountered on `bancomoc.mz` (plain `requests` with `verify=False` returned HTTP 200 immediately), and all 9 Jira lists were successfully extracted from the single source file.
- The `Actividades` column (present only for Bancos, containing identical multi-paragraph legal boilerplate for every bank) was deliberately not mapped to any field — it carries no per-entity information.
