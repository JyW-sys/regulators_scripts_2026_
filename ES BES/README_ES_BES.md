# ES BES — Banco de España

Jira: **DECD-6467** (parent epic DECD-3438 — Regulators 2026 — Crawlers)

Latest scraper: **`ES BES_v_1.3.ipynb`** — a rebuild, not a patch (see below).

Entry point: `http://app.bde.es/ren_www/ren_wwwias/xml/Arranque.html`

## Lists

19 lists, from two report screens. `ListLabel`: 1 = bank, 4 = everything else — Banco de España
does not supervise insurance at all (that is the DGSFP), so no 2 or 3 appears here.

| ListCode | Entity-type code | ListName | ListLabel | Last run |
|---|---|---|---|---|
| 1 | BP | BANCOS | 1 | 42 |
| 2 | CA | CAJAS DE AHORROS | 1 | 2 |
| 3 | CC | COOPERATIVAS DE CREDITO | 1 | 60 |
| 4 | CO | CREDITO OFICIAL | 1 | 1 |
| 5 | EDE | ENTIDADES DE DINERO ELECTRONICO | 4 | 12 |
| 6 | EP | ENTIDADES DE PAGO | 4 | 51 |
| 7 | EFC | ESTABLECIMIENTOS FINANCIEROS DE CREDITO | 4 | 22 |
| 8 | OR | OFICINAS DE REPRESENTACION … DE ENTIDADES DE CREDITO EXTRANJERAS | 1 | 29 |
| 10 | SGR | SOCIEDADES DE GARANTIA RECIPROCA | 4 | 17 |
| 11 | SR | SOCIEDADES DE REAFIANZAMIENTO | 4 | 1 |
| 12 | ST | SOCIEDADES DE TASACION | 4 | 28 |
| 14 | SECC | SUCURSALES DE ENT. DE CREDITO EXTRANJERAS COMUNITARIAS | 1 | 78 |
| 15 | SECE | SUCURSALES DE ENT. DE CREDITO EXTRANJERAS EXTRACOMUNITARIAS | 1 | 3 |
| 16 | SEDC | SUCURSALES DE ENT. DE DINERO ELECTRONICO EXTRANJERAS COMUNITARIAS | 4 | 10 |
| 17 | SEPC | SUCURSALES DE ENT. DE PAGO EXTRANJERAS COMUNITARIAS | 4 | 11 |
| 18 | ECVM | TITULARES DE ESTABLECIMIENTOS DE COMPRA Y VENTA DE MONEDA EXTRANJERA | 4 | 17 |
| 19 | 21 | ENT. CTO. COMUN. OPER. ESPAÑA SIN ESTAB. (ART. 39 DIR. 2013/36/CE) | 1 | 666 |
| 20 | 11.2 | ENT. CTO. EXTRACOM. OPER. ESPAÑA SIN ESTAB. (ART. 6, LEY 10/2014) | 1 | 3 |
| 22 | 19 | ENT. FINAN., FILIALES ENT. CTO. COMUN., OPER. ESPAÑA SIN ESTAB. (ART. 34) | 4 | 20 |

## Why this was a rebuild, not a patch

Banco de España rebuilt the IAS application (page footer now reads "© 2022"). `Arranque.html`
still returns 200, but **every anchor the old scraper depended on is gone**:

- `#CBTipoEntidad`, the entity-type dropdown the whole loop was driven from, is absent from the
  DOM — there are now **zero `<select>` elements** on the screen.
- `#TableDataRejillaConPaginacionEnServidor` (the results grid), `#btnDetalle` / `#btnVolver`
  (the per-entity drill-down) and `.paginationNumber` are all gone.
- The "Tablas maestras" screen now states outright *"Esta consulta ha sido deshabilitada."*

v1.2 caught this in a bare `except:` that printed `failed go to reg` and `continue`d, so all 19
lists failed, `sqldict` stayed empty, and it wrote a **0-row Excel without erroring** — a silent
failure. There was no surviving anchor to patch against.

## How v1.3 works

The two search screens now emit **one JasperReports XLS each**, covering every entity type at
once. So instead of ~1,100 sequential detail page-loads, the scraper downloads two files and
groups by entity-type column.

Selenium is still required: the IAS session handshake mints a per-session `IdUnico` UUID, and a
plain `requests` POST without it is rejected with HTTP 400.

Recipe per screen:

1. `GET Arranque.html`
2. click `//*[@id="AreaDeNavegacioncolMapa_0"]/ul/li[1]/ul/li[1]` (con establecimiento) or
   `.../li[2]` (sin establecimiento)
3. JS-click **both** radio groups — `_GrupoRadioButton_0` (*Actual*; `_1` = *Completa*, which
   also returns cancelled entities) and `_GrupoRadioButton0_0` (*Entidades*; `_1` =
   *Actividades*). Both are mandatory: submitting without them returns
   *"Error 001: Seleccionar dato"* instead of a file.
4. click `#btnBuscar` → `informe_EntConEstab.xls` (~348 KB) / `informe_EntSinEstab.xls` (~141 KB)

Then `pandas.read_excel(..., engine='xlrd')` and group by `COD_TIPO` (ConEstab, 49 columns) /
`TIPO_ENTIDAD` (SinEstab, 10 columns). Those two columns hold exactly the entity-type codes in
the table above.

**`xlrd` is required** — these are legacy BIFF8 `.xls`; `openpyxl` cannot read them.

## Notes

- **Encoding is fine on this route.** BIFF8 stores Unicode natively, so `ñ` and accents decode
  clean (`DEUTSCHE BANK, SOCIEDAD ANONIMA ESPAÑOLA`). The ISO-8859-1 concern that applies to
  `www.bde.es` error pages does not apply here.
- **6 entity types are in the file but not in the ticket** — `EFEP` (9), `EPEX` (14), `PSIC` (5),
  `SEFC` (1), `SFC` (7), `SFMC` (1) = **37 rows**, skipped. The scraper prints a `[WARN]` naming
  them rather than dropping them silently, so a future scope change is visible. Raise with the
  ticket owner if any of these should be added.
- **Address fields only exist for the ConEstab lists.** The SinEstab report (ListCodes 19, 20, 22
  — 689 of the 1073 rows) has no address, postcode, phone or website columns at all, which is why
  `Address_1` / `City` / `Zip` sit at ~36 %. That is a source limitation, not a parse gap.
- **New fields the old scraper never captured**, now emitted: `CODIGO_LEI` → `LEI Code`,
  `TELEFONO` → `Phone`, `NUMFAX` → `Fax`, `DIRINTERNET` → `Website`, `POBLACION` → `City`,
  `CODPOSTAL` → `Zip`, `FECHAALTA` → `RegulationDate`, `FCHBAJA` → `CancellationDate`, and the
  whole `…ENTMATRIZ` parent-company block.

## Last run

2026-07-29 — **1073 rows**, 43 columns, all 19 ListCodes present, counts matching the register
exactly (data load 25/06/2026, "Actual" filter). `ListLabel` and `Cntry` 100 % filled, no
encoding flags.
