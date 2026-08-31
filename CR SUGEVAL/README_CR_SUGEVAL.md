# CR SUGEVAL — Registro Nacional de Valores e Intermediarios

Jira: **DECD-6825**
Regulator: Superintendencia General de Valores (SUGEVAL), Costa Rica — the **securities** supervisor.
Scraper: `CR_SUGEVAL_v2.py` / `CR_SUGEVAL_v2.ipynb`
Last real run: **2026-08-20**, output `CR SUGEVAL SQL Ready 2026-08-20 18.45.17.xlsx` — **178 rows × 43 columns**.

---

## 1. Lists

This ticket defines **one list**, not nine. The nine participant categories are sub-parts of the
same register and are carried in `Typology` / `CoType`, not in `ListName`.

| ListNr | ListCode | ListLabel | ListName | URL | Source type | Rows |
|---|---|---|---|---|---|---|
| 1 | `1` | `4` | Registro Nacional de Valores e Intermediarios | `https://serviciosexternos.sugeval.fi.cr/RNVIWeb/Participantes/TodosParticipantes` | JSON POST endpoint behind a DataTables grid | **178** |

`ListLabel = 4` ("everything else"): SUGEVAL supervises the securities market, not banks or
insurers. See §6 for the *Grupos Financieros* caveat.

---

## 2. The URL on the ticket is stale — please update it

**The host in the Jira description, `https://aplicaciones.sugeval.fi.cr/...`, is dead.**

Observed on 2026-08-20 from the Mac dev box:

* DNS resolves to `181.193.118.175` and `181.193.30.47`; **TCP :443 connects on both**, but the
  TLS handshake is **reset by peer** (`ConnectionResetError 54`).
* Headless Chrome — direct *and* via the corporate proxy — rendered Chrome's `ERR_CONNECTION_RESET`
  interstitial. Note that interstitial is ~185 KB of markup, so a naive "did I get bytes back?"
  check reports success. Length is not a liveness test on this site.
* Through the corporate proxy, `requests` got `ProxyError` / a 120 s hang.

The register now lives on **`https://serviciosexternos.sugeval.fi.cr/RNVIWeb/...`**, which
`https://www.sugeval.fi.cr/` itself links to. That host answers plain `requests` with HTTP 200.

> **Not verified:** whether `aplicaciones.sugeval.fi.cr` is globally dead or merely unreachable
> from this corporate network. This should be re-checked from the Windows production box before
> anyone tells the requester the URL is definitively wrong. Everything else in this README was
> observed directly.

---

## 3. How the data is actually retrieved

The category pages ship **no `<table>`** — the grid is a DataTables widget hydrated by AJAX.
The v1 approach (click `btnExportar`, poll `tempfolder` for a downloaded workbook) has been
dropped as fragile. v2 talks to the backend directly, in three steps per category:

1. **Harvest** the category paths at runtime from `https://www.sugeval.fi.cr/`, matching
   `/RNVIWeb/Participantes/<Slug>`. Nothing is hard-coded — a further re-platforming produces a
   loud `SKIPPED`, not a silent zero-row file.
2. **GET** the category page and pull two things out of the markup:
   * `__RequestVerificationToken` — the ASP.NET anti-CSRF token (hidden input);
   * `data-alias-consulta` on `<form id="formConsultaPrincipal">` — the backend query alias
     (e.g. `PuestosBolsa` → `GeneralPuestoBolsa`). The alias is **not** derivable from the slug
     (`Emisores` → `GeneralEmisor`, `OtrosParticipantes` → `GeneralOtrosParticipantesRnvi`,
     `GruposFinancieros` → `GeneralGrupoFinancieros`), so it must be read from the page.
3. **POST** to `/RNVIWeb/BackendAPI/ObtenerDatosPrincipal/<alias>` with
   `parametros={"IdParticipante":"0","CodEstado":"I","FechaDesde":"","FechaHasta":"","EstadoParaBolsa":"0"}`,
   five repeated `urlParametros[]` values, and `esGet=false`.

**The response is double-encoded JSON** — a JSON *string* whose content is the JSON array.
`json.loads()` must be applied twice. Decoding once yields a string and any `[0]` index silently
returns a character, which is exactly how this looks like a parse failure when it is not.

`CodEstado="I"` = **INSCRITO** (currently registered), i.e. the positive register.

### Fallback
A DrissionPage browser fallback (`fetch_category_browser`) is wired in and fires automatically if
the plain-requests path returns zero rows. It captures the same XHR via `page.listen.start()`.
It was used during discovery but **the final run did not need it** — all nine categories came back
through plain `requests`.

---

## 4. Field mapping

Source columns: `IdParticipante`, `CodRol`, `NombreParticipante`, `Estado`, `Rol`, `Regulador`, `CodEstado`.

| Output field | Source | Note |
|---|---|---|
| `Name` | `NombreParticipante` | |
| `InternalID_1` / `_type` | `IdParticipante` / `'Codigo de participante SUGEVAL'` | fixed-width, trailing spaces stripped |
| `InternalID_2` / `_type` | `CodRol` / `'Codigo de rol'` | |
| `CoType` | `Rol` | e.g. `PUESTO DE BOLSA`, `AUDITOR EXTERNO ELEGIBLE` |
| `License_Type` | `Regulador` | supervising body (`BOLSA NACIONAL DE VALORES`, `SUPERINTENDENCIA…`); **empty for Auditores Externos** — the source does not supply it. Judgment call, see §6 |
| `Typology` | category label | e.g. `Puestos de bolsa` |
| `RegulationType` | constant `'Regulated'` | the query filters to INSCRITO only |
| `ListLabel` / `ListCode` / `ListName` | `4` / `1` / see §1 | |
| `Cntry`, `RegCtry` | `CR` | |
| `RegCode` | `SUGEVAL` | |
| `ListLanguage` | `ES` | |
| `ListProcessDate` | `now.strftime('%Y-%m-%d')` | |

All 178 records are written through a single `add_row(**kw)` that appends to **every one of the 43
keys on every record** and raises `KeyError` on an unknown key. The writer also asserts
`list(df.columns) == SCHEMA_KEYS` before saving, so column drift cannot reach the workbook.

`Estado` is not mapped: with the INSCRITO filter it is constant. `RegulationDate` /
`CancellationDate` are left blank — this endpoint returns no dates at all, so no `parse_date()`
was needed.

---

## 5. Row-count reconciliation (run of 2026-08-20)

| Category | Alias | Rows |
|---|---|---|
| Auditores externos | `GeneralAuditoresExternos` | 67 |
| Emisores | `GeneralEmisor` | 47 |
| Custodios | `GeneralCustodios` | 22 |
| Puestos de bolsa | `GeneralPuestoBolsa` | 16 |
| SAFI | `GeneralSAFI` | 13 |
| Calificadoras de riesgo | `GeneralCalificadoras` | 4 |
| Grupos financieros | `GeneralGrupoFinancieros` | 4 |
| Proveedor de precios | `GeneralProveedorPrecio` | 3 |
| Otros participantes | `GeneralOtrosParticipantesRnvi` | 2 |
| **TOTAL** | | **178** |

Verified from the saved workbook: 178 rows, 43 columns, 0 blank names, `ListLabel` uniformly `4`,
`RegulationType` uniformly `Regulated`.

The site does not publish its own KPI counter for these grids, so there is no
declared-vs-scraped figure to compare against. **No deduplication is performed** — an entity that
holds several roles appears once per role, which is what the site renders (e.g. `ACOBO PUESTO DE
BOLSA, S.A.` appears under both *Custodios* and *Puestos de bolsa*).

### Out of scope — counts supplied so the requester can opt in

| Category | Path prefix | Rows | Why excluded |
|---|---|---|---|
| Agentes Corredores | `/Participantes/` | **194** | ticket says skip |
| Sociedades Fiduciarias | `/Participantes/` | **0** | ticket says skip (also currently empty) |
| Sociedades Titularizadoras | `/Participantes/` | **0** | ticket says skip (also currently empty) |
| Entidad Registro Centralizado | `/OtrosParticipantes/` | **2** | different path prefix — not "under Participantes" |

Note the prefix distinction: `/RNVIWeb/Participantes/OtrosParticipantes` **is** in scope (2 rows);
`/RNVIWeb/OtrosParticipantes/EntidadRegistroCentralizado` is not.
`/Participantes/TodosParticipantes` is the aggregate landing page — its backend returns `null`, and
it is skipped as a page rather than a category.

---

## 6. Judgment calls for the requester

1. **`ListLabel = 4` for the whole list.** *Grupos Financieros* (4 rows) contains financial groups
   that may include banking entities. Treated as one securities list rather than split; flagging
   in case the requester wants `3` for the list or those rows re-labelled.
2. **`License_Type` ← `Regulador`.** The 43-key schema has no natural home for "supervising body".
   `License_Type` was the closest fit. Empty for all 67 *Auditores Externos* because the source
   omits it. Happy to move it to an `InternalID_3` slot if preferred.
3. **Agentes Corredores (194 rows)** is by far the largest category and is skipped per the ticket.
   Worth confirming that is still intended — these are individual broker agents (natural persons),
   which is the likely reason for the exclusion.
4. **Ticket URL needs updating** to the `serviciosexternos` host (§2).
5. **Only INSCRITO entities are captured.** Revoked/suspended participants are reachable by
   changing `CodEstado`, and would be a separate list with a different `RegulationType`. Not built.

---

## 7. What changed vs v1, and why

v1 (`CR_SUGEVAL_v1.ipynb`, left on disk untouched) was broken in five ways:

1. **Dead host.** Pointed at `aplicaciones.sugeval.fi.cr` — every list fails today.
2. **Hard-coded Windows path** (`C:\Users\wuj1\...`) as `scriptfolder`; could not run on macOS.
   v2 uses the `__file__` / `os.getcwd()` try-except.
3. **34-key `sqldict`** — missing the 9 LEI / BIC / mother-company keys. v2 uses the fixed 43-key
   schema verbatim, enforced by `add_row` plus a pre-save assert. v1's `bourange_same_length_array`
   back-filling trick is gone; every row now writes every key.
4. **Selenium + `btnExportar` + poll `tempfolder`** — depended on a real browser, a download
   directory, and `sleep(10)`/`sleep(30)` guesses. v2 uses three `requests` calls per category.
5. **Dropped two of three columns** (took only `data.columns[0]`), and wrote the workbook with no
   `sheet_name='SQL Ready'` and no `df['Name'] != ''` filter. All fixed.

v1's stored outputs also totalled 178, but the per-category split differs (Auditores 66→67,
Emisores 48→47, Puestos 15→16, Proveedores 2→3, Otros 4→2) — ordinary register churn since that
run. The matching total is coincidence, not a checksum.

---

## 8. Site quirks that will break this scraper later

* **F5 Shape / BIG-IP bot defence.** The pages load `/TSPD/<hex>?type=9`. A bare `requests`
  session worked on 2026-08-20, but this is exactly the layer that starts issuing JS challenges
  without notice — and it is the most likely cause of the `aplicaciones.` host resetting
  connections. **Treat the requests path as fragile.** The DrissionPage fallback exists for this;
  if it also starts failing, the response will not parse as JSON and the run prints
  `SKIPPED — response was not JSON (bot-defence challenge?)`.
* **The query alias is not derivable from the URL slug.** Never hard-code it; always read
  `data-alias-consulta` from the page.
* **Double-encoded JSON** (§3) — the single most likely thing to be "fixed" incorrectly by a
  future maintainer who sees `json.loads` called twice and removes one.
* **Anti-CSRF token is per-page-load.** It must be fetched fresh with each category page; reusing
  one across categories was not tested.
* **Fixed-width padding.** Every string field arrives space-padded from the database
  (`"AGENTPB        "`); `clean()` strips it. Do not compare these raw.
* **Corporate TLS proxy** — `verify=False` plus `disable_warnings()` throughout. A cert error here
  is the proxy, not the site.
* The two currently-empty categories (*Sociedades Fiduciarias*, *Sociedades Titularizadoras*)
  return `0` rather than an error, so an empty result is not by itself evidence of breakage.

---

## 9. Run

```bash
python3 "CR SUGEVAL/CR_SUGEVAL_v2.py"
```

The notebook `CR_SUGEVAL_v2.ipynb` is generated from the `.py` by splitting on the
`#---- Begin_<name> ----` markers (`Librairie`, `fileName`, `Variable`, `Function`, `MainLoop`,
`writer and save df to excel`) and was executed end-to-end with nbclient on 2026-08-20:
**6 cells, 0 with `output_type == 'error'`.**

Output `.xlsx` is written to the `CR SUGEVAL/` folder (not `tempfolder/`), sheet `SQL Ready`.
