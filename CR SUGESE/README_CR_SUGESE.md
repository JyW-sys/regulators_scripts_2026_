# CR SUGESE — Superintendencia General de Seguros (Costa Rica)

Jira: **DECD-6821**  ·  `RegCtry = CR`  ·  `RegCode = SUGESE`  ·  `ListLanguage = ES`

| File | Purpose |
|---|---|
| `CR_SUGESE_v1.py` | The scraper (production). |
| `CR_SUGESE_v1.ipynb` | Same code split into the standard cells; generated from the `.py` and executed end-to-end. |
| `CR SUGESE SQL Ready <timestamp>.xlsx` | Output, sheet `SQL Ready`. |
| `tempfolder/` | Downloads / intermediates. |

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source | Rows |
|---|---|---|---|---|---|---|
| 1 | 1 | 2 | Aseguradoras | `/cr/es/mercado-seguros/aseguradoras.html` | Power BI — *Aseguradoras activas* | 12 |
| 2 | 2 | 2 | Sociedades agencias de seguros | `/cr/es/mercado-seguros/sociedades-agencia.html` | Power BI — *Sociedades Agencia activas* | 22 |
| 3 | 3 | 2 | Sociedades corredoras | `/cr/es/mercado-seguros/sociedades-corredoras.html` | Power BI — *Sociedades corredoras activas* | 38 |
| 4 | 4 | 2 | Operadores Activos de Seguros Autoexpedibles | `/cr/es/mercado-seguros/operadores-de-seguros-autoexpedibles.html` | Power BI — *Operadores…activos* | 103 |
| 5 | 5 | 2 | Proveedores de seguros transfronterizos | `/cr/es/mercado-seguros/seguros-transfronterizos.html` | HTML table | 1 |
| 6 | 6 | **4** | Grupos financieros | `/cr/es/mercado-seguros/grupos-financieros.html` | HTML table | 5 |
| 7 | 7 | 2 | Autorizaciones condicionadas | `/cr/es/mercado-seguros/autorizaciones-condicionadas.html` | HTML table | 2 |

Base host: `https://www.sugese.fi.cr`.  **Total: 183 rows.**

**ListLabel choice.** SUGESE is the insurance supervisor, so lists 1–5 and 7 are `2` (insurance).
List 6 *Grupos financieros* is the membership of the financial conglomerates — a fund manager, a
brokerage house, a health-services company and the insurer — i.e. mixed non-insurance entities,
so it is `4` (everything else).

---

## Site quirks

### 1. The site was re-platformed — the old `/seccion-mercado-seguros/` paths are dead
SUGESE moved to Adobe AEM. Every legacy
`https://www.sugese.fi.cr/seccion-mercado-seguros/<slug>` URL returns **HTTP 404** (verified
2026-08-20, all seven); the live pages are `/cr/es/mercado-seguros/<slug>.html` — same slugs,
new prefix and a `.html` suffix. The DECD-6821 description already carries the new URLs, so
**nothing needs to be written back to the ticket**; only older notes and any inherited code still
point at the dead paths.

The Power BI report tokens did **not** change during the re-platform — the `r=` token in the
ticket's list-4 link still resolves. Only the landing pages moved.

### 2. Lists 1, 2 and 3 are now Power BI too — not just list 4
The ticket only flagged list 4 as a Power BI report. After the re-platform, **lists 1–3 are also
Power BI "publish to web" embeds**; there is no HTML table left on those pages. Consequently the
ticket's instructions for lists 1–3 no longer apply as written:

* *"Clicking each company name opens a PDF with address + contact info"* (list 1) — **no longer
  true and no longer needed.** Address, phone, e-mail and website are columns inside the report,
  so no PDF is downloaded or parsed.
* *"the number after `Personería jurídica:` = InternalID_1"* (lists 2, 3) — that number is now the
  report's `Identificacion` column, which is what the scraper maps to `InternalID_1`.

Each page carries several reports (*activas* / *inactivas* / *canceladas* / *suspendidos*). The
scraper reads the report links off the landing page and picks the **"activas / activos"** one by
its link label, so only active entities are extracted.

### 3. How the Power BI data is actually extracted
No browser is required — it is three plain `requests` calls:

1. `GET https://app.powerbi.com/view?r=<token>` → scrape `resolvedClusterUri` out of the page.
   The value is the `…-redirect` load-balancer host; the data plane answers on the same name with
   `-redirect` swapped for **`-api`** (currently `wabi-paas-1-scus-api.analysis.windows.net`).
   Hitting the `-redirect` host, or `api.powerbi.com`, returns **403**.
2. `GET  {cluster}/public/reports/{resourceKey}/modelsAndExploration?preferReadOnlySession=true`
   → the `modelId` (**GET**, not POST — POST returns 404).
   `POST {cluster}/public/reports/conceptualschema` → every entity + property in the model.
3. `POST {cluster}/public/reports/querydata?synchronous=true` → the data.

All three need the header `X-PowerBI-ResourceKey: <k>`, where `k` comes from base64-decoding the
`r=` query-string parameter (`{"k": "...", "t": "..."}`).

Because the schema is read from `conceptualschema` at run time, the scraper asks for **all**
properties of the fact table rather than a hard-coded column list, and it can join the companion
licence/date table (`Aseguradoras Activas`, `Agencias activas`, `Corredoras activas`) in the same
query — Power BI resolves the join through the model relationships.

The response is Power BI's compressed **DSR** format, decoded by `pbi_decode()`: bitmask `R` marks
columns repeated from the previous row, bitmask `Ø` marks nulls, and integer values are indexes
into the per-column `ValueDicts`.

`ListValidityDate` is the report's own refresh stamp (*"Última fecha de actualización: …"*). It is
a **measure**, not a column, so it needs a `Select: [{Measure: …}]` query — asking for it as a
column returns an empty result set.

### 4. Messy date fields
`Fecha inscripción` / `Fecha autorización` are free text. Observed shapes:
`18/06/2009`, `No aplica` (INSTITUTO NACIONAL DE SEGUROS — created by special law, so it has no
authorisation date and `RegulationDate` is left blank), `11/27/2009` (stray US month/day order),
and multi-line blobs such as `Generales:\n19/02/2010\nPersonales:\n19/07/2011`. List 6 writes dates
in Spanish words (`Sesión 822-2009 del 11 de diciembre de 2009`).
`parse_date()` handles all of these — including Spanish month names and epoch-millisecond values
from Power BI — and keeps the **earliest** date when several are present.

### 5. Encoding
Pages are UTF-8 and decode cleanly (`r.content.decode('utf-8')`); the output was checked for
mojibake (`Ã`, `Â`, `�`) and is clean. Note the source model itself contains a typo,
`CorreoElectronicoOficinaPrincial` (not *Principal*) — the scraper uses the misspelled name.

---

## Field mapping

Common to every row: `RegulationType = 'Regulated'`, `RegCtry = 'CR'`, `RegCode = 'SUGESE'`,
`ListLanguage = 'ES'`, `Cntry = 'CR'` (except list 5), `ListProcessDate = now.strftime('%Y-%m-%d')`.

### List 1 — Aseguradoras
| Column | Source |
|---|---|
| Name | `RazonSocial` |
| InternalID_1 / _type | `Identificacion` / `Trade Register Number` |
| InternalID_2 / _type | `Licencia` / `License Number` |
| CoType | `Tipo entidad` |
| License_Type | `Categoria` (G = generales, P = personales, G-P = both) |
| Address_1 / Phone / Email | `Direccion` / `Telefono` / `CorreoElectronico` |
| Website | `Sitio web` |
| RegulationDate | `Fecha inscripción`, falling back to `Fecha autorización` |

### Lists 2 & 3 — Sociedades agencias / corredoras
| Column | Source |
|---|---|
| Name | `RazonSocial` |
| InternalID_1 / _type | `Identificacion` (the *Personería jurídica* number) / `Trade Register Number` |
| InternalID_2 / _type | `NumLicencia` / `License Number` |
| License_Type | `Exclusiva` (list 2 only — *Exclusivo* / *No exclusivo*) |
| Address_1 / Phone | `Direccion` / `Telefono` |
| Name - Mother Company | `AseguradoraAcredita` (list 2 only — **see judgment call below**) |
| RegulationDate | `Fecha inscripción`, falling back to `Fecha autorización` |

`Email`, `Website` and `City` come out **empty for all 60 rows** of lists 2 and 3. That is the
source, not a mapping gap — the two semantic models were dumped from `conceptualschema` on
2026-08-20 and contain no e-mail, website, province or cantón field anywhere. The complete set of
usable columns is:

* **list 2** (`DES vi_DESInformacionSociedadesAgenciasActivas`): `RazonSocial`, `Identificacion`,
  `NumLicencia`, `Exclusiva`, `Direccion`, `Telefono`, `TelefonoSecundario`, `Ramos`,
  `AseguradoraAcredita` — plus `Licencia`, `Fecha autorización`, `Fecha inscripción` on the joined
  `Agencias activas` table.
* **list 3** (`DES vi_DESInformacionSociedadesCorredorasActivas`): `RazonSocial`, `Identificacion`,
  `NumLicencia`, `Direccion`, `Telefono`, `TelefonoSecundario` — plus the same date columns on
  `Corredoras activas`.

Two of those are collected but not written anywhere, because the fixed schema has no home for
them: **`TelefonoSecundario`** (a second phone, not a fax — putting it in `Fax` would be wrong) and
**`Ramos`** (lines of business, list 2 only; `License_Type` is already taken by *Exclusiva*).
Say so if either should be appended to `Phone` / `License_Type`.

### List 4 — Operadores de seguros autoexpedibles activos
Mapping agreed with the requester in the ticket comments. **Principal office only** — the
`…ServicioAlCliente` address/phone/e-mail columns are deliberately ignored, except the website.

| Column | Source |
|---|---|
| Name | `RazonSocialOperador` (*Nombre o razón social*) |
| InternalID_1 / _type | `IdentificacionOperador` (*Identificación*) / `Trade Register Number` |
| InternalID_2 / _type | `CodigoRegistro` / `License Number` |
| Address_1 | `DireccionOficinaPrincipal` (*Dirección de oficina principal*) |
| Address_2 / City | `ProvinciaOficinaPrincipal` / `CantonOficinaPrincipal` |
| Phone | `TelefonoOficinaPrincipal` |
| Email | `CorreoElectronicoOficinaPrincial` |
| Website | `SitioWebServicioAlCliente` (*Sitio web de servicio al cliente*) |
| RegulationDate | `FechaRegistro` (epoch ms) |
| Name - Mother Company | `Entidad` (the accrediting insurer — **see judgment call below**) |

### List 5 — Proveedores de seguros transfronterizos
`Name` ← *Entidad* · `InternalID_1` ← *Código* (`License Number`) · `License_Type` ←
*Tipo de Licencia* · `Cntry` ← mapped from *Jurisdicción* (`Estados Unidos de América …` → `US`) ·
`RegulationDate` ← *Fecha Registro* · `ListValidityDate` ← *Vigencia registro*.

**`Address_1` is deliberately empty.** *Jurisdicción* is the provider's home jurisdiction, not a
street address, so it only feeds `Cntry`; writing the country name into `Address_1` as well would
duplicate it in the wrong field. Cross-border providers have no address on the page — by design,
since they operate in Costa Rica without physical presence.

### List 6 — Grupos financieros
`Name` ← *Entidad* · `Name - Mother Company` ← *Grupo* · `Typology` ← *Supervisora* ·
`Address_1` ← *Dirección* · `Cntry` ← from *Domicilio* · `RegulationDate` ← date parsed out of
*Incorporación*.

### List 7 — Autorizaciones condicionadas
`Name` ← *Entidad* · `InternalID_1` ← *Autorización* (`License Number`) · `License_Type` ←
*Tipo de Autorización* · `RegulationDate` ← *Fecha de Autorización*.

---

## Row counts — reconciliation with the site

Counts were verified against what the site itself renders, by capturing the `querydata` responses
the live Power BI embeds issue (headless Chrome) and counting the rows in the table visual.

| List | Scraper | Site | Reconciles |
|---|---|---|---|
| 1 Aseguradoras | 12 | 12 | yes |
| 2 Sociedades agencia | 22 | 22 | yes |
| 3 Sociedades corredoras | 38 | 38 | yes |
| 4 Operadores autoexpedibles | 103 | 103 | yes |
| 5 Transfronterizos | 1 | 1 | yes |
| 6 Grupos financieros | 5 | 5 | yes |
| 7 Autorizaciones condicionadas | 2 | 2 | yes |
| **Total** | **183** | | |

**List 2 — 22 rows, 20 distinct companies.** A sociedad agencia accredited by two insurers gets one
row per accreditation, and the site's table shows all 22. The rows are **not** deduplicated, so the
output matches the site row-for-row.

**List 4 — 103 rows, 85 distinct operators.** The two numbers on the page are not in conflict:
*"Total de operadores únicos 85"* is a KPI **measure** counting distinct `IdentificacionOperador`,
while the table below it renders **103 rows**. The scraper reproduces the table.

14 operators account for the 32 rows that share a cédula. Every one of those duplicate groups
carries a **different `CodigoRegistro` and a different `FechaRegistro`** on each row (14/14 in both
cases) — each row is a separate registration, not a repeat. Banco BAC, for example:

| Código de registro | Fecha registro | Entidad (accrediting insurer) |
|---|---|---|
| `OA-A01-0001` | 2010-08-25 | INSTITUTO NACIONAL DE SEGUROS |
| `OA-A05-0050` | 2013-06-04 | ASSA COMPAÑÍA DE SEGUROS |
| `OA-A07-0043` | 2015-02-19 | (third accreditation) |

Other per-row differences within the duplicate groups: principal address 14/14, e-mail 10/14,
website 9/14, phone 6/14. Collapsing to 85 would therefore mean **throwing away real data**, not
removing redundancy. Consistent with the standing repo rule that output row count must match what
the site renders (cf. GB IMFSC 666 vs 780).

---

## Judgment calls for the requester to confirm

1. **`Name - Mother Company` used for the accrediting insurer** (list 2 `AseguradoraAcredita`,
   list 4 `Entidad`). The fixed output schema has no field for an accreditation relationship, and
   for list 2 it is the only thing distinguishing the two pairs of otherwise identical rows.
   Strictly this insurer is the intermediary's *principal*, not its parent. **Decision: keep it.**
   Dropping it would leave list 2's duplicate accreditation rows indistinguishable from each other
   and would discard the only insurer link the source publishes. If the requester disagrees, remove
   the `Name - Mother Company=` argument from the list 2 / list 4 `add_row()` calls — nothing else
   depends on it.
2. **List 7 `RegulationType = 'Regulated'`.** *Autorizaciones condicionadas* are entities that have
   been authorised but whose entry into operation is still conditional on meeting the requirements
   of articles 22 and 24. They are not yet operating, so a different `RegulationType` may be more
   accurate. `'Regulated'` was applied per the ticket instruction.
3. **List 6 includes `Instituto Nacional de Seguros`**, which also appears in list 1. That is what
   the source shows — INS is both an authorised insurer and a member of Grupo INS.

*Resolved 2026-08-20:* list 5's *Vigencia registro* (`07/04/2027`) now populates
`ListValidityDate`. It is not a cancellation, so `CancellationDate` stays blank.

---

## Two column choices that look wrong on screen but are not

### "Entidad" on lists 2, 3, 5, 6, 7 vs "Entidad" on list 4 — different things
The ticket says *"the column **Entidad** is the company name"* for **lists 2 and 3 only**. Those
two Power BI models contain **no field named `Entidad`**; their fields are
`RazonSocial`, `Identificacion`, `NumLicencia`, `Direccion`, `Telefono`, … The rendered table
header reads *Entidad* while the underlying model field is `RazonSocial`, which holds
`SOCIEDAD AGENCIA DE SEGUROS AGS, S.A.` etc. So `Name ← RazonSocial` **is** the requested column;
the display header and the field name simply differ.

List 4's model does have a real `Entidad` field, but it means something else entirely — the
**accrediting insurer** (`ASSA COMPAÑÍA DE SEGUROS, S.A.`, `INSTITUTO NACIONAL DE SEGUROS`, …).
Putting it in `Name` would turn a 103-row list of operators into the same handful of insurers
repeated, with the operators lost. Guilherme's comment of 2025-01-24 settles list 4 explicitly:
*"collect the name from the column «Nombre o razón social»"*.

For lists 5, 6 and 7 the pages are plain HTML and the header really is `Entidad`, so those map
directly.

### List 4 `Name` — `RazonSocialOperador`, not `NombreComercial`
Both fields exist on every row. `NombreComercial` is the **brand**, not the company:

| `RazonSocialOperador` (used) | `NombreComercial` |
|---|---|
| Banco Nacional De Costa Rica | `BN` |
| Banco De Costa Rica | `BCR` |
| Banco Bac San Jose Sociedad Anonima | `BAC Credomatic` |
| Cooperativa De Ahorro Y Credito Alianza De Perez Zeledon R L | `COOPEALIANZA R.L.` |
| 3-102-731585 Sociedad De Responsabilidad Limitada | `Segurvending` |

Across the 103 rows the two agree (after accent/suffix normalisation) on only **16**. Decisive
point: there are **85 distinct `IdentificacionOperador` and 85 distinct `RazonSocialOperador`** —
a clean 1:1 with the cédula jurídica — but **97 distinct `NombreComercial`**, because the same
legal entity files a different trade name under different insurers (Banco BAC is
`BANCO BAC SAN JOSÉ, S.A.` on its ASSA row and `BAC Credomatic` on its INS row). Using
`NombreComercial` would give one legal entity two different names.

Caveat: the report's visible column header may read *Nombre comercial*, so output and screen will
not match cell-for-cell. That is intentional — the legal name is what downstream matching needs.

`RazonSocialOperador` arrives from SUGESE with accents stripped and suffixes spelled out
(`Banco Bac San Jose Sociedad Anonima`, not `Banco BAC San José, S.A.`). That is the source's own
formatting; no normalisation is applied.
