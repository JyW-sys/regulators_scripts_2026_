# BO ASFI — Autoridad de Supervisión del Sistema Financiero (Bolivia)

Jira: **DECD-6977**
Site: https://www.asfi.gob.bo (Spanish only — no English edition of this register exists)
Scraper: `BO_ASFI_v_3.py` / `BO_ASFI_v_3.ipynb`
Run observed: 2026-09-03 — **67 rows total**, output `BO ASFI SQL Ready 2026-09-03 12.00.15.xlsx`

ASFI supervises the whole Bolivian financial system, but the register this ticket covers is
specifically *entidades de intermediación financiera* — banks, housing entities, savings &
credit cooperatives and development finance institutions. No insurance entity appears on it.

---

## Lists

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows (observed) |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | Entidades Supervisadas Con Licencia De Funcionamiento | https://www.asfi.gob.bo/la/entidades-intermediacion-financiera-licencia-funcionamiento | PDF (`Listado general …`), joined to `Siglas …` PDF | 67 |
| | | | | | **TOTAL** | **67** |

The ticket comment scopes the list to the **first PDF** on the page,
*"Listado general de las entidades de intermediación financiera con licencia de funcionamiento
04_2026.pdf"*. That PDF alone defines the row set.

### ListLabel justification (1 = bank, 2 = insurance, 3 = both, 4 = other)

**ListLabel = 1.** Every one of the 67 entities is a deposit-taking financial-intermediation
entity licensed under the Ley N° 393 de Servicios Financieros: bancos múltiples, bancos PYME,
state banks, entidades financieras de vivienda, cooperativas de ahorro y crédito, and
instituciones financieras de desarrollo. There is no insurance entity on this register — ASFI
publishes insurance under a separate register that this ticket does not cover — so `3` would
be wrong, and `4` would understate a list that is entirely banking.

### RegulationType

`RegulationType = 'Regulated'` on all 67 rows. The register is by definition the positive list
of entities holding a **Licencia de Funcionamiento** (recorded verbatim in `License_Type`).

The same page also publishes three *negative* registers — **en Liquidación**, **en Proceso de
Intervención**, and **en Proceso de Quiebra**. These are **deliberately not scraped**: the
ticket scopes this list to the first PDF, and those entities do not hold an operating licence.
If they are ever wanted they need their own ListNr and a non-`Regulated` RegulationType —
they must not be folded into list 1.

---

## Source structure and why two PDFs are read

### `Name` is the Listado name column, verbatim — by decision, not by accident

The Listado is laid out as six category blocks. The entity category sits in the block's
top-left header cell, and the name column then carries only the **remainder** of the legal
name. Row 1 of *Bancos Múltiples* literally reads `Nacional de Bolivia S.A.` — not
`Banco Nacional de Bolivia S.A.` — and the cooperativas read `Abierta "Jesús Nazareno" R.L.`

**Decision (ticket owner, 2026-09-03): take the name column as published; do not prepend
the block header.** Rationale given:

- the category is already carried in `CoType`, so repeating it inside `Name` is duplicated
  data, and
- prefixing it makes all 41 cooperativas share a ~39-character prefix
  (`Cooperativa de Ahorro y Crédito Abierta`), which inflates pairwise string similarity
  between genuinely distinct entities and degrades downstream entity matching.

So **`Name` in this output is deliberately not the full legal name.** The only cleanup
applied is stripping a trailing footnote marker such as `(1)`. Consumers who need the
official full name will find it in the Siglas PDF this script already downloads.

An earlier build of v3 did populate `Name` from the Siglas PDF; that output
(`BO ASFI SQL Ready 2026-09-03 12.00.15.xlsx`) is superseded. For reference, the two forms:

| Listado name column (**used**) | ASFI official full name (not used) |
|---|---|
| `Nacional de Bolivia S.A.` | `Banco Nacional de Bolivia S.A.` |
| `De la Comunidad S.A.` | `Banco PYME de la Comunidad S.A.` |
| `La Primera` | `La Primera Entidad Financiera de Vivienda` |
| `Abierta "Jesús Nazareno" R.L.` | `Cooperativa de Ahorro y Crédito Abierta "Jesús Nazareno" R.L.` |
| `CIDRE - IFD` | `Institución Financiera de Desarrollo CIDRE IFD` |

Note that the *Entidades Financieras del Estado* block is not truncated in the Listado at
all (`Banco de Desarrollo Productivo S.A.M.`), so those two rows are unaffected either way.

### The Siglas PDF is still read — for `InternalID_1` only

The same page publishes *Siglas de Entidades de Intermediación Financiera*, which lists the
identical 67 entities with their full official name and a **3-character ASFI sigla**.
v3 joins to it purely to populate `InternalID_1` (67/67, all unique); it no longer touches
`Name`. The Listado drives the row set (as the ticket requires) and supplies `Name` and
`City` (*Oficina Central*).

**The two PDFs are not in the same order**, so they cannot be zipped positionally —
"Madre y Maestra" is entry 8 in the Siglas cooperativas block but entry 24 in the Listado.
Joining by position would have silently mislabelled roughly 30 cooperativas. The join is by
normalised name (accent-folded, punctuation-stripped), scoped to the matching category block:

1. **Containment** — the Listado stub is a substring of the official name. 66/67 matched here.
2. **Residual** — one category ended with exactly one unmatched row and exactly one unclaimed
   sigla, which are by construction each other's partner. 1/67 matched here, and the run
   prints a warning naming both sides so it stays visible.

Residual pairing exists because the two PDFs **disagree on one name**: the Listado says
`DIACONÍA FRIF - IFD`, the Siglas say `DIACONÍA FRID - IFD` (F/D transposition — one is a
typo). Lowering a fuzzy-match threshold until that pair matched would also have let genuine
mismatches through, so the deterministic residual rule is used instead. Since `Name` now
comes from the Listado, **the output carries the Listado spelling** `DIACONÍA FRIF - IFD`;
only the sigla `IDI` comes from the Siglas side.

A row that fails to join simply gets an empty `InternalID_1`, and is reported — never
silently guessed and never dropped. `Name` is unaffected by the join outcome.
Observed 2026-09-03: **0 unmatched**.

### Pagination

None. Both sources are single PDF downloads (4 pages and 3 pages). The PDF links are
**resolved at runtime by link text**, never hard-coded: the filename carries the edition
(`…04_2026.pdf`) and the directory carries the publication month (`/2026-05/`), so both
change every month and a hard-coded URL would quietly serve a stale edition forever.

### Two parsing traps in the Siglas PDF

Both produced a plausible-looking 67/67 total while individual category blocks were wrong —
the reason this scraper reconciles **per category**, not just on the grand total:

- the sigla `VL1` contains a digit, so an `[A-Z]{3}` code pattern silently drops it;
- the header `ENTIDADES FINANCIERAS DEL ESTADO O CON PARTICIPACIÓN MAYORITARIA / DEL ESTADO`
  wraps, and the continuation line `DEL ESTADO` parses as a well-formed entry with code
  `DEL` and name `ESTADO`.

Handled by an alphanumeric code pattern plus the rule that an entry name must contain a
lowercase letter (ALL-CAPS lines are headers, never entities).

---

## Field mapping

| Source | sqldict key | Notes |
|---|---|---|
| Listado — name column, **verbatim** | `Name` | Spanish, accents intact, never translated; block header deliberately not prepended (see above); only a trailing `(n)` footnote marker stripped |
| Siglas — 3-char code | `InternalID_1` | with `InternalID_1_type = 'ASFI sigla'`; 67 unique |
| Listado — category block header | `CoType` | e.g. `Bancos Múltiples`, `Cooperativas de Ahorro y Crédito Abiertas y Societarias` |
| Listado — *Oficina Central* | `City` | |
| (constant) | `License_Type` | `Licencia de Funcionamiento` |
| Siglas footnote *"A partir del … cuenta con Licencia de Funcionamiento"* | `RegulationDate` | ISO date; 11 rows |
| Listado — *"Información actualizada al 30 de abril de 2026"* | `ListValidityDate` | `2026-04-30` |
| (constant) | `Cntry`, `RegCtry` = `BO`; `RegCode` = `ASFI`; `ListCode` = `1` | the three tokens of the folder name |
| (constant) | `RegulationType` = `Regulated`, `ListLanguage` = `ES`, `ListLabel` = `1` | |
| Jira ListName | `ListName`, `Typology` | verbatim from the ticket |
| run date | `ListProcessDate` | `%Y-%m-%d` |

`RegulationDate` is populated only where a footnote actually **states a licence date**. The
footnotes are a mixed bag — some describe a 2014 legal reclassification or the IDEPRO/SEMBRAR
SARTAWI merger — so the phrase *"cuenta con Licencia de Funcionamiento"* is required, not
merely the presence of a footnote marker.

---

## Row reconciliation (run of 2026-09-03)

| Category block | PDF rows | Output rows |
|---|---|---|
| Bancos Múltiples | 11 | 11 |
| Bancos PYME | 2 | 2 |
| Entidades Financieras del Estado | 2 | 2 |
| Entidades Financieras de Vivienda | 3 | 3 |
| Cooperativas de Ahorro y Crédito | 41 | 41 |
| Instituciones Financieras de Desarrollo | 8 | 8 |
| **TOTAL** | **67** | **67** |

Every block's running numbers are contiguous `1..n`, which is the script's single strict
acceptance test — it is the property that actually catches a dropped row or a lost page break
(the cooperativas block spans a page break at entry 21/22).

The per-category counts measured on the `04_2026` edition are recorded in the script. The PDF
is reissued monthly, so drift is reported as a **warning**, not a failure.

### Field completeness (67 rows)

| Field | Non-empty | % |
|---|---|---|
| `Name` | 67 | 100% |
| `InternalID_1` | 67 | 100% |
| `CoType` | 67 | 100% |
| `City` | 61 | 91% |
| `RegulationDate` | 11 | 16% |
| `Address_1`, `Phone`, `Website`, `Email`, `Zip` | 0 | 0% |

---

## Known limitations

- **`Address_1`, `Phone`, `Website`, `Email`, `Zip` are empty.** Neither PDF carries them, and
  the ticket scopes this list to the PDF. `City` (*Oficina Central*) is the only location data
  published.
- **Six cities are blank** — cooperativas 13, 28, 32, 33, 34 and 40 (`Asunción`, `Progreso`,
  `San Pedro de Aiquile`, `Virgen de los Remedios`, `San Francisco Solano`, `Cantera`). This
  was verified against the raw PDF **text layer**, not just the extracted table cells: the
  *Oficina Central* column really is empty in the source. Left blank rather than guessed.
- **The `DIACONÍA FRIF / FRID` discrepancy is unresolved upstream.** v3 pairs them for the
  sigla and emits the **Listado** spelling `DIACONÍA FRIF - IFD` in `Name`. If ASFI corrects
  one PDF the containment match will start succeeding and the warning disappears on its own.
- **`Name` is not the full legal name** — it is the Listado name column as published, which
  for most blocks omits the entity category (`Abierta "Jesús Nazareno" R.L.`,
  `Nacional de Bolivia S.A.`). This is the ticket owner's explicit choice for matching
  reasons; see the section above. Anything downstream that expects a registry-style legal
  name needs to account for it.
- **Departmental coverage is dropped.** The Listado carries an `x`-matrix of the nine
  departments each entity operates in. There is no `sqldict` field for it.
- **Negative registers are out of scope** — see *RegulationType* above.

## Language

Scraped from the **Spanish** source; there is no English edition of these PDFs. `Name` keeps
its original Spanish spelling and is never translated, so 54 of the 67 names carry accented
characters. The run asserts that no mojibake (`Ã©`, `â€™`, `Â `, `Ã±`, `ï¿½`) and no run of
three or more `?` reaches `Name` or `City`, and that identifiers survive the Excel round-trip
as text rather than being coerced to floats.

Nothing scraped is ever printed raw — the Windows control server console is cp1252 and raises
`UnicodeEncodeError` on Spanish accents and `ñ`, so all console output goes through an
ASCII-slug helper.
