# SV SSF

## Regulator Information

- **Country/Region Code**: SV
- **Regulator Code**: SSF
- **Full Name**: Superintendencia del Sistema Financiero (El Salvador)
- **Website**: https://ssf.gob.sv/
- **Jira**: DECD-6300

## Script

- **Current Version**: `SV_SSF_v1.py`
- **Approach**: Static HTML, `requests` + `BeautifulSoup` (no browser/JS needed). `verify=False` for the corporate TLS proxy, desktop User-Agent, `urllib3.disable_warnings`. A small retry wrapper (`get_soup`) handles the occasional proxy timeout.
- **Language**: Content is Spanish. Entity **Names are kept verbatim in Spanish** (not translated). `ListLanguage='ES'`.

## Lists

10 lists, all merged into ONE output file. `ListCode` = ListNr. English glosses are for the reviewer only — data values are unchanged.

| ListNr | ListName (Spanish, verbatim) | English gloss | ListLabel | Extraction | Rows |
|-------|------------------------------|---------------|-----------|-----------|------|
| 1 | Bancos privados | Private banks | 1 | accordion (title=name) + detail table | 10 |
| 2 | Bancos cooperativos | Cooperative banks | 1 | accordion, **two URLs merged** | 7 |
| 3 | Bancos estatales | State banks | 1 | accordion | 4 |
| 4 | Sucursales de bancos extranjeros | Foreign-bank branches | 1 | heading (`h4`) + table | 1 |
| 5 | Sociedades proveedoras de dinero electronico | E-money providers | 4 | accordion | 2 |
| 6 | Sociedades de Ahorro y Credito | Savings & credit companies | 1 | accordion + detail table | 4 |
| 7 | Entidades autorizadas para operar como sociedades de seguros y fianzas | Insurance & surety companies | 2 | accordion | 24 |
| 8 | Entidades autorizadas para operar como casas de cambio | Exchange houses | 4 | accordion | 1 |
| 9 | Entidades autorizadas para operar en el mercado de valores | Securities-market entities | 4 | **nested** accordion (category → `h5` names) | 37 |
| 10 | Entidades autorizadas del sistema previsional | Pension-system entities | 4 | **nested** accordion (category → `li` names) | 6 |
| | | | | **TOTAL** | **96** |

## Page structure (WordPress + Elementor)

Three layouts, handled by three functions in the script:

1. **`scrape_accordion_title_list`** (lists 1, 2, 3, 5, 6, 7, 8) — each `.elementor-accordion-item` is ONE entity: the `.elementor-accordion-title` is the **Name**; the `.elementor-tab-content` holds the detail block (a `<table>` on lists 1 & 6, `<p>` lines elsewhere).
2. **`scrape_table_heading_list`** (list 4) — the entity Name is the `h4.wp-block-heading` immediately before a `<table>` of details.
3. **`scrape_nested_accordion`** (lists 9, 10) — each `.elementor-accordion-item` is a **category** (e.g. "Casas corredoras de bolsa"); the entities live inside it. Names are `<h5>` headings (list 9) or `<li>` items (list 10); the `<p>` lines that follow each name are its details. The category label is stored in **CoType**.

### Detail parsing (`parse_fields`)

Both `Label: value` (inline) and `Label` / `value` (label on its own line, value on the next) forms occur. `parse_fields` normalises both and pulls:

- **Address_1** ← `Dirección`
- **Website** ← `Sitio Web` / `Página web`
- **Phone** ← `Teléfono` / `Tel`
- **Email** ← `Correo` / `Email`

People/other labels (`Presidente`, `Gerente General`, `Fax`, `Apoderado`, …) are recognised only so their values are **consumed and discarded**, never mistaken for entity data. `Ver Junta Directiva` links are ignored.

## Field mapping

| sqldict field | Source / value |
|---------------|----------------|
| Name | accordion title / heading / `h5` / `li` (Spanish, verbatim) |
| Address_1 | `Dirección` (full address string; not split) |
| Website | `Sitio Web` / `Página web` when present |
| Phone | `Teléfono` / `Tel` when present |
| Email | `Correo` when present (rare) |
| CoType | category label (lists 9 & 10 only) |
| Cntry | `SV` |
| RegulationType | `Regulated` |
| RegCtry / RegCode / ListCode | `SV` / `SSF` / ListNr |
| ListName | exact Spanish name (see table) |
| ListLabel | see table |
| ListLanguage | `ES` |
| ListProcessDate | run date (`%Y-%m-%d`) |

## ListLabel decisions

Per project rule (1=bank, 2=insurance, 3=both, 4=other):

- **1 (bank)** — lists 1, 2, 3, 4, 6 (private / cooperative / state banks, foreign branches, savings-&-credit societies).
- **2 (insurance)** — list 7 (seguros y fianzas).
- **4 (other)** — list 5 (e-money), 8 (exchange houses), 9 (securities market), 10 (pension system).

## Notes / QA

- **96 entities total**, no empty names, no duplicates within a list, no duplicates across lists.
- **Field availability varies by page** — SSF publishes an address for almost every entity, a website/phone for many, and an email for almost none (only 1, in list 10). The two name-only categories in list 9 ("Almacenes generales de depósito", "Puestos de bolsa de productos y servicios") list names without contact details, which is why list 9's detail-fill is lower than its row count. This reflects the source, not a parse failure.
- **City / Zip left blank**: the site embeds the locality inside the free-text address; it is not published as a separate field, so it is kept in `Address_1` rather than guessed.
- **List 2 merges two pages** (cooperative banks *authorised* and *not authorised* to take deposits); both carry `ListCode=2`, `ListName='Bancos cooperativos'`.
- **List 10 source duplication**: the pension page renders its two categories twice (two Elementor widgets with slightly different content). The script de-duplicates by Name within each list, yielding the 6 distinct entities (2 AFPs + 4 state pension institutes).
- **FLAG — list 4 name truncated at source**: the page's heading HTML literally reads `Citibank, N.A., Sucursal El Salva` (cut off in SSF's CMS). Kept verbatim as published; the intended full name is *Citibank, N.A., Sucursal El Salvador*. Reviewer may want to correct.
- **FLAG — list 7 suspended entity**: `Pan American Life Insurance Company (Sucursal El Salvador) Suspendida` carries a "Suspendida" (suspended) tag on the page. Name kept verbatim and `RegulationType='Regulated'` per ticket rule — flag for QA if a different status is preferred.
- **Run output** saved into this folder as `SV SSF SQL Ready <timestamp>.xlsx`.
