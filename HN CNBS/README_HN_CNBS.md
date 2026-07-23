# HN CNBS — Comisión Nacional de Bancos y Seguros (Honduras)

Jira: [DECD-5025](https://moodysdatapipeline.atlassian.net/browse/DECD-5025) (parent epic DECD-3438)

## Source

A single official **Excel** workbook, *"Instituciones Supervisadas por la CNBS - Marzo 2026.xlsx"*
(Spanish). The public page `https://www.cnbs.gob.hn/instituciones-supervisadas` **redirects** to
the real host `publicaciones.cnbs.gob.hn`, where the file is served by an ASP.NET download route:

```
https://publicaciones.cnbs.gob.hn/Home/Download/
  Instituciones%20Supervisadas%2FListado%20de%20Instituciones%2F2026/
  1.%20Instituciones%20Supervisadas%20por%20la%20CNBS%20-%20Marzo%202026.xlsx
```

The `%2F` segments **must stay percent-encoded** (they are route data, not path separators);
hitting `www.cnbs.gob.hn` or decoding the `%2F` returns a 404 HTML page. The scraper downloads
with `requests` and reads the workbook with pandas.

## Extraction

The workbook has 8 sheets; only **`REPORTE`** is the entity list
(*"INSTITUCIONES SUPERVISADAS POR LA CNBS, Al 31 de marzo de 2026"*). The other sheets are
office-count statistics by department/year and are ignored.

`REPORTE` layout (data in columns 1–5; column 0 is a spacer):

| col | meaning |
|---|---|
| 1 | `No.` (or a category header / `Subtotal`) |
| 2 | `Institución` → **Name** |
| 3 | `Nombre de Referencia` (brand/abbrev — not captured) |
| 4 | `Fecha Inicio de Operaciones` (operations start — not mapped) |
| 5 | `Oficina Principal (Ciudad)` → **City** |

Rows are walked top-to-bottom: a row with a numeric `No.` is an institution; a non-numeric,
non-`Subtotal`/header text row sets the current **category**, which is stored as **`Typology`**
(e.g. *Bancos Comerciales*, *Instituciones de Seguros*, *Casas de Bolsa*). Repeated title/header
blocks and `Subtotal` rows are skipped.

**No translation applied:** institution names and city names are proper nouns; the only Spanish
text kept verbatim is the `Typology` classification label. Accented characters are preserved
(valid UTF-8 — the Windows console renders them as `�`, but the file is correct).

## Output

`tempfolder/HN CNBS SQL Ready <timestamp>.xlsx`, sheet **"SQL Ready"**, standard `sqldict` schema.

- `RegCtry`=HN, `RegCode`=CNBS, `Cntry`=HN, `ListLanguage`=Spanish.
- `ListName`=`Instituciones Supervisadas por la CNBS`, `ListCode`=1.
- `Typology`=institution category. `RegulationType`=**Regulated**. `ListProcessDate`=run date.

## Run

```
python "HN CNBS/HN CNBS_v1.py"
```

## Last run (2026-06-10) — 84 entities (= all 84 numbered rows in REPORTE)

21 categories, e.g. Bancos Comerciales 15 · Instituciones de Seguros 12 · Sociedades Financieras 9 ·
Casas de Bolsa 6 · Institutos Públicos de Previsión Social 5 · Organizaciones Privadas de Desarrollo
Financieras 5 · Administradoras de Fondos de Pensiones 4 · Almacenes Generales de Depósito 4 ·
Sociedades Remesadoras de Dinero 4 · Bancos Estatales 3 · Procesadoras de Tarjetas 3 · … (+10 more).

Name/City/Typology 100% filled, 0 duplicates, accents intact.
